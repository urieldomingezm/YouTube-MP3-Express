from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import yt_dlp
import os
import time

from youtubesearchpython import VideosSearch

app = Flask(__name__)
app.secret_key = 'descarga-audio'

import platform
if 'vercel' in os.environ.get('PATH', '').lower() or platform.system() == 'Linux':
    RUTA_DESCARGA = '/tmp/descargar'
else:
    RUTA_DESCARGA = 'descargar'

if not os.path.exists(RUTA_DESCARGA):
    os.makedirs(RUTA_DESCARGA)

import re
from datetime import datetime

def limpiar_url_youtube(url):
    url = re.sub(r'([&?](list|index|start_radio|t|ab_channel|pp)=.*?)(?=&|$)', '', url)
    url = re.sub(r'[&?]+$', '', url)
    return url

def descargar_audio(url, progress_hook=None):
    info = None
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception:
            info = None
    artista_abrev = 'Desconocido'
    if info:
        import re
        artista = info.get('artist')
        if artista:
            pass
        else:
            titulo = info.get('title', '')
            if '-' in titulo:
                artista = titulo.split('-')[0].strip()
            else:
                artista = info.get('uploader', 'Desconocido')
        artista = artista.lower()
        artista = re.sub(r'[áàäâ]', 'a', artista)
        artista = re.sub(r'[éèëê]', 'e', artista)
        artista = re.sub(r'[íìïî]', 'i', artista)
        artista = re.sub(r'[óòöô]', 'o', artista)
        artista = re.sub(r'[úùüû]', 'u', artista)
        artista = re.sub(r'[^a-z0-9\-\s]', '', artista)
        artista = re.sub(r'\s+', ' ', artista).strip()
        palabras = artista.split()
        if len(palabras) > 2:
            artista_abrev = ' '.join([p.capitalize() for p in palabras[:2]])
        else:
            artista_abrev = ' '.join([p.capitalize() for p in palabras])
        if not artista_abrev:
            artista_abrev = 'Desconocido'
    carpeta_artista = os.path.join(RUTA_DESCARGA, artista_abrev)
    if not os.path.exists(carpeta_artista):
        os.makedirs(carpeta_artista)
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{carpeta_artista}/%(title)s.%(ext)s',
        'noplaylist': True,
        'progress_hooks': [progress_hook] if progress_hook else [],
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }
        ]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    for root, dirs, files in os.walk(RUTA_DESCARGA):
        for f in files:
            if f.endswith('.mp3'):
                ruta = os.path.join(root, f)
                os.utime(ruta, (time.time(), time.time()))

def obtener_archivos_descargados():
    archivos = []
    ahora = time.time()
    LIMITE_SEGUNDOS = 24*60*60
    if os.path.exists(RUTA_DESCARGA):
        for root, dirs, files in os.walk(RUTA_DESCARGA):
            for f in files:
                if f.endswith('.mp3'):
                    ruta = os.path.join(root, f)
                    try:
                        creado = os.path.getmtime(ruta)
                    except Exception:
                        creado = ahora
                    tiempo_restante = int(LIMITE_SEGUNDOS - (ahora - creado))
                    if tiempo_restante <= 0:
                        os.remove(ruta)
                    else:
                        rel_path = os.path.relpath(ruta, RUTA_DESCARGA)
                        archivos.append({'nombre': rel_path, 'tiempo_restante': tiempo_restante})
    return archivos

def actualizar_progreso(d, progress_data):
    if d['status'] == 'downloading':
        progress_data['progress'] = float(d.get('downloaded_bytes', 0)) / float(d.get('total_bytes', 1) or 1) * 100
        progress_data['status'] = 'downloading'
    elif d['status'] == 'finished':
        progress_data['progress'] = 100
        progress_data['status'] = 'converting'

progress_data = {'progress': 0, 'status': 'idle'}

@app.route('/', methods=['GET', 'POST'])
def index():
    global progress_data
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            url = limpiar_url_youtube(url)
            progress_data = {'progress': 0, 'status': 'downloading'}
            try:
                descargar_audio(url, progress_hook=lambda d: actualizar_progreso(d, progress_data))
                flash('¡Descarga completada!', 'success')
            except Exception as e:
                flash(f'Error: {e}', 'danger')
            progress_data = {'progress': 0, 'status': 'idle'}
        else:
            flash('Por favor, ingresa una URL.', 'warning')
        return redirect(url_for('index'))
    archivos = obtener_archivos_descargados()
    return render_template('index.html', archivos=archivos, now=datetime.now)

@app.route('/progreso')
def progreso():
    return jsonify(progress_data)

from urllib.parse import unquote

@app.route('/descargar/<path:nombre_archivo>')
def descargar_archivo(nombre_archivo):
    nombre_archivo = unquote(nombre_archivo)
    ruta = os.path.join(RUTA_DESCARGA, nombre_archivo)
    if os.path.exists(ruta):
        return send_file(ruta, as_attachment=True, download_name=os.path.basename(nombre_archivo), mimetype='audio/mpeg')
    flash('Archivo no encontrado.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/buscar')
def buscar():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'resultados': []})
    vs = VideosSearch(query, limit=8)
    resultados = []
    for v in vs.result().get('result', []):
        resultados.append({
            'titulo': v['title'],
            'url': v['link'],
            'miniatura': v['thumbnails'][0]['url'] if v['thumbnails'] else '',
            'canal': v['channel']['name'] if 'channel' in v and 'name' in v['channel'] else '',
            'duracion': v.get('duration', '')
        })
    return jsonify({'resultados': resultados})

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import yt_dlp
import os
import time

# Para búsqueda de videos en YouTube
from youtubesearchpython import VideosSearch

# --- Endpoint de búsqueda de videos de YouTube ---


app = Flask(__name__)
app.secret_key = 'descarga-audio'


# Usar /tmp en Vercel para archivos temporales
import platform
if 'vercel' in os.environ.get('PATH', '').lower() or platform.system() == 'Linux':
    RUTA_DESCARGA = '/tmp/descargar'
else:
    RUTA_DESCARGA = 'descargar'

if not os.path.exists(RUTA_DESCARGA):
    os.makedirs(RUTA_DESCARGA)


# --- Funciones auxiliares ---
import re
from datetime import datetime

def limpiar_url_youtube(url):
    """Limpia parámetros de playlist y otros extras de la URL de YouTube."""
    url = re.sub(r'([&?](list|index|start_radio|t|ab_channel|pp)=.*?)(?=&|$)', '', url)
    url = re.sub(r'[&?]+$', '', url)
    return url

def descargar_audio(url, progress_hook=None):
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{RUTA_DESCARGA}/%(title)s.%(ext)s',
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
    # Actualiza la fecha de creación del archivo mp3 a ahora
    for f in os.listdir(RUTA_DESCARGA):
        if f.endswith('.mp3'):
            ruta = os.path.join(RUTA_DESCARGA, f)
            os.utime(ruta, (time.time(), time.time()))

def obtener_archivos_descargados():
    """Obtiene la lista de archivos mp3 válidos y elimina los expirados."""
    archivos = []
    ahora = time.time()
    LIMITE_SEGUNDOS = 24*60*60  # 1 día
    if os.path.exists(RUTA_DESCARGA):
        for f in os.listdir(RUTA_DESCARGA):
            if f.endswith('.mp3'):
                ruta = os.path.join(RUTA_DESCARGA, f)
                try:
                    creado = os.path.getmtime(ruta)
                except Exception:
                    creado = ahora
                tiempo_restante = int(LIMITE_SEGUNDOS - (ahora - creado))
                if tiempo_restante <= 0:
                    os.remove(ruta)
                else:
                    archivos.append({'nombre': f, 'tiempo_restante': tiempo_restante})
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

# Endpoint para consultar el progreso
@app.route('/progreso')
def progreso():
    return jsonify(progress_data)


@app.route('/descargar/<nombre_archivo>')
def descargar_archivo(nombre_archivo):
    ruta = os.path.join(RUTA_DESCARGA, nombre_archivo)
    if os.path.exists(ruta):
        return send_file(ruta, as_attachment=True, download_name=nombre_archivo, mimetype='audio/mpeg')
    flash('Archivo no encontrado.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

# --- Endpoint de búsqueda de videos de YouTube ---
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

import yt_dlp

def descargar_audio(url):
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': 'descargar/%(title)s.%(ext)s',
        'extract_audio': True,
        'audio_format': 'mp3',
        'noplaylist': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

if __name__ == "__main__":
    url = input("Ingresa URL de YouTube: ")
    descargar_audio(url)

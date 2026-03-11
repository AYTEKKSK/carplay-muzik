# -*- coding: utf-8 -*-
"""
YouTube Müzik - Bağımsız Flask Uygulaması
Port: 5051
Erişim: http://localhost:5051  veya  app.articnc.online/muzik
"""
import os, sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except: pass

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, render_template, session, send_from_directory
import yt_dlp

from music_database import (
    init_database, create_playlist, get_user_playlists,
    get_global_playlist, add_song_to_playlist,
    remove_song_from_playlist, get_playlist_songs,
    delete_playlist, rename_playlist
)

app = Flask(__name__)
app.secret_key = 'muzik-standalone-secret-2026'

# ── DB Init ─────────────────────────────────────────────────────────────────
init_database()
global_pl = get_global_playlist()
if not global_pl:
    create_playlist("Herkez'in Şarkıları", is_global=True)
    print("[OK] Global playlist olusturuldu")

# ── Cache klasörü ────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'yt_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Yardımcı ─────────────────────────────────────────────────────────────────
def format_duration(seconds) -> str:
    if not seconds:
        return "0:00"
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"

# ══════════════════════════════════════════════════════════════════════════════
#  SAYFALAR
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/install')
def install():
    return render_template('install.html')

@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-precomposed.png')
def apple_touch_icon():
    return send_from_directory(app.static_folder, 'apple-touch-icon.png')

# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO STREAM API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/get-audio-stream', methods=['POST'])
def get_audio_stream():
    try:
        data = request.json
        video_id = data.get('video_id') or data.get('videoId')
        if not video_id:
            return jsonify({'success': False, 'error': 'video_id gerekli'}), 400

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cachedir': CACHE_DIR,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
            audio_url = None
            audio_format = None
            if 'formats' in info:
                audio_formats = [f for f in info['formats']
                                 if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                if audio_formats:
                    best = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                    audio_url = best.get('url')
                    audio_format = best.get('ext', 'unknown')
            if not audio_url and 'url' in info:
                audio_url = info['url']
                audio_format = info.get('ext', 'unknown')
            if not audio_url:
                return jsonify({'success': False, 'error': 'Audio stream bulunamadı'}), 404
            return jsonify({
                'success': True,
                'audio_url': audio_url,
                'audioUrl': audio_url,
                'format': audio_format,
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', '')
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  MUSIC SEARCH + PLAYLIST API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/music/search', methods=['POST'])
def search_youtube():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = data.get('max_results', 10)
        if not query:
            return jsonify({'error': 'Arama sorgusu gerekli'}), 400
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist', 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if not result or 'entries' not in result:
                return jsonify({'results': []})
            videos = []
            for entry in result['entries']:
                if entry and entry.get('id'):
                    vid = entry['id']
                    videos.append({
                        'video_id': vid,
                        'title': entry.get('title', 'Bilinmeyen'),
                        'channel': entry.get('uploader') or entry.get('channel') or 'YouTube',
                        'duration': format_duration(entry.get('duration', 0)),
                        'thumbnail': entry.get('thumbnail') or f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                        'url': f"https://www.youtube.com/watch?v={vid}"
                    })
            return jsonify({'results': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/music/playlists/my', methods=['GET'])
def get_my_playlists():
    user_id = session.get('user_id', 'guest')
    return jsonify({'playlists': get_user_playlists(user_id)})


@app.route('/api/music/playlists/global', methods=['GET'])
def get_global_playlist_api():
    playlist = get_global_playlist()
    if not playlist:
        return jsonify({'error': 'Global playlist bulunamadı'}), 404
    playlist['songs'] = get_playlist_songs(playlist['id'])
    return jsonify({'playlist': playlist})


@app.route('/api/music/playlists/create', methods=['POST'])
def create_playlist_api():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Playlist ismi gerekli'}), 400
    user_id = session.get('user_id', 'guest')
    playlist_id = create_playlist(name, user_id, is_global=False)
    return jsonify({'success': True, 'playlist_id': playlist_id})


@app.route('/api/music/playlists/<int:playlist_id>/songs', methods=['GET'])
def get_playlist_songs_api(playlist_id):
    return jsonify({'songs': get_playlist_songs(playlist_id)})


@app.route('/api/music/playlists/<int:playlist_id>/add-song', methods=['POST'])
def add_song_api(playlist_id):
    data = request.get_json()
    video_data = data.get('video_data')
    if not video_data:
        return jsonify({'error': 'Video verisi gerekli'}), 400
    user_id = session.get('user_id', 'guest')
    success = add_song_to_playlist(playlist_id, video_data, user_id)
    # Global playlist'e de ekle
    try:
        gpl = get_global_playlist()
        if gpl and gpl['id'] != playlist_id:
            add_song_to_playlist(gpl['id'], video_data, user_id)
    except Exception:
        pass
    return jsonify({'success': success, 'message': 'Şarkı eklendi' if success else 'Zaten var'})


@app.route('/api/music/playlists/<int:playlist_id>/remove-song/<int:song_id>', methods=['DELETE'])
def remove_song_api(playlist_id, song_id):
    user_id = session.get('user_id', 'guest')
    success = remove_song_from_playlist(playlist_id, song_id, user_id)
    return jsonify({'success': success})


@app.route('/api/music/playlists/<int:playlist_id>', methods=['DELETE'])
def delete_playlist_api(playlist_id):
    user_id = session.get('user_id', 'guest')
    success = delete_playlist(playlist_id, user_id)
    return jsonify({'success': success})


@app.route('/api/music/playlists/<int:playlist_id>/rename', methods=['PUT'])
def rename_playlist_api(playlist_id):
    new_name = request.get_json().get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'Yeni isim gerekli'}), 400
    user_id = session.get('user_id', 'guest')
    success = rename_playlist(playlist_id, new_name, user_id)
    return jsonify({'success': success})


@app.route('/api/music/init-default-playlists', methods=['POST'])
def init_default_playlists():
    user_id = session.get('user_id', 'guest')
    existing = get_user_playlists(user_id)
    if len(existing) >= 3:
        return jsonify({'success': True, 'message': 'Zaten mevcut'})
    defaults = ['Favoriler', 'En Sevdiğim Şarkılar', 'Çalma Listem']
    created = []
    for name in defaults:
        if not any(p['name'] == name for p in existing):
            pid = create_playlist(name, user_id, is_global=False)
            created.append({'id': pid, 'name': name})
    return jsonify({'success': True, 'created': created})


# ══════════════════════════════════════════════════════════════════════════════

# ── PWA ──────────────────────────────────────────
@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(app.static_folder, 'manifest.json',
                               mimetype='application/manifest+json')

@app.route('/sw.js')
def pwa_sw():
    resp = send_from_directory(app.static_folder, 'sw.js',
                               mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp
# ─────────────────────────────────────────────────

if __name__ == '__main__':
    print("[OK] YouTube Muzik baslatiliyor -> http://localhost:5051")
    print("   Internet: app.articnc.online/muzik")
    app.run(host='0.0.0.0', port=5051, debug=True)

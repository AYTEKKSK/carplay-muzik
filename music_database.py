# -*- coding: utf-8 -*-
"""
Music Playlist Database Manager
Kullanıcı playlist'leri ve global playlist için veritabanı yönetimi
"""
import sqlite3
import json
import os
from typing import List, Dict, Optional, Any
from datetime import datetime

# DB dosyası bu modülün yanında
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'music_playlists.db')

def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id TEXT,
            is_global INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlist_songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            title TEXT NOT NULL,
            channel TEXT,
            duration TEXT,
            thumbnail TEXT,
            added_by TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            position INTEGER DEFAULT 0,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_playlist_songs_playlist ON playlist_songs(playlist_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_playlists_user ON playlists(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_playlists_global ON playlists(is_global)')
    conn.commit()
    conn.close()
    print("[OK] Music database initialized:", DATABASE_PATH)

def create_playlist(name: str, user_id: Optional[str] = None, is_global: bool = False) -> int:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO playlists (name, user_id, is_global) VALUES (?, ?, ?)',
                   (name, user_id, 1 if is_global else 0))
    playlist_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return playlist_id

def get_user_playlists(user_id: str) -> List[Dict]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, COUNT(ps.id) as song_count
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        WHERE p.user_id = ? AND p.is_global = 0
        GROUP BY p.id ORDER BY p.created_at DESC
    ''', (user_id,))
    playlists = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return playlists

def get_global_playlist() -> Optional[Dict]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, COUNT(ps.id) as song_count
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        WHERE p.is_global = 1
        GROUP BY p.id LIMIT 1
    ''')
    row = cursor.fetchone()
    playlist = dict(row) if row else None
    conn.close()
    return playlist

def add_song_to_playlist(playlist_id: int, video_data: Dict, user_id: str) -> bool:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM playlist_songs WHERE playlist_id = ? AND video_id = ?',
                       (playlist_id, video_data.get('video_id')))
        if cursor.fetchone():
            conn.close()
            return False
        cursor.execute('SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_songs WHERE playlist_id = ?',
                       (playlist_id,))
        next_pos = cursor.fetchone()[0]
        cursor.execute('''
            INSERT INTO playlist_songs (playlist_id, video_id, title, channel, duration, thumbnail, added_by, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (playlist_id, video_data.get('video_id'), video_data.get('title'),
              video_data.get('channel'), video_data.get('duration'),
              video_data.get('thumbnail'), user_id, next_pos))
        cursor.execute('UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (playlist_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Add song: {e}")
        conn.close()
        return False

def remove_song_from_playlist(playlist_id: int, song_id: int, user_id: str) -> bool:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, is_global FROM playlists WHERE id = ?', (playlist_id,))
        playlist = cursor.fetchone()
        if not playlist or playlist[1] == 1 or playlist[0] != user_id:
            conn.close()
            return False
        cursor.execute('DELETE FROM playlist_songs WHERE id = ? AND playlist_id = ?', (song_id, playlist_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Remove song: {e}")
        conn.close()
        return False

def get_playlist_songs(playlist_id: int) -> List[Dict]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM playlist_songs WHERE playlist_id = ? ORDER BY position ASC, added_at DESC',
                   (playlist_id,))
    songs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return songs

def delete_playlist(playlist_id: int, user_id: str) -> bool:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, is_global FROM playlists WHERE id = ?', (playlist_id,))
        playlist = cursor.fetchone()
        if not playlist or playlist[1] == 1 or playlist[0] != user_id:
            conn.close()
            return False
        cursor.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Delete playlist: {e}")
        conn.close()
        return False

def rename_playlist(playlist_id: int, new_name: str, user_id: str) -> bool:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, is_global FROM playlists WHERE id = ?', (playlist_id,))
        playlist = cursor.fetchone()
        if not playlist or playlist[1] == 1 or playlist[0] != user_id:
            conn.close()
            return False
        cursor.execute('UPDATE playlists SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                       (new_name, playlist_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Rename playlist: {e}")
        conn.close()
        return False

import sqlite3
import os
from flask import g

DB_PATH = os.path.join("instance", "steamcatalog.db")

print("=== DB DEBUG ===")
print("DB PATH:", DB_PATH)
print("ABS PATH:", os.path.abspath(DB_PATH))
print("DB EXISTS:", os.path.exists(DB_PATH))
try:
    print("INSTANCE CONTENTS:", os.listdir("instance"))
except Exception as e:
    print("INSTANCE ERROR:", e)
print("===============")


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
        DB_PATH,
        timeout=15,
        check_same_thread=False
    )

        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    os.makedirs("instance", exist_ok=True)
    db = sqlite3.connect(DB_PATH)

    # Users
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        steamid TEXT UNIQUE,
        display_name TEXT,
        avatar_url TEXT
    );
    """)

    # Games metadata
    db.execute("""
    CREATE TABLE IF NOT EXISTS games (
        appid INTEGER PRIMARY KEY,
        title TEXT,
        cover_url TEXT,
        custom_cover_url TEXT,
        description TEXT,
        genres TEXT,
        release_year INTEGER,
        tags TEXT
    );
    """)


    # NEW: Owned games table
    db.execute("""
    CREATE TABLE IF NOT EXISTS owned_games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        steamid TEXT,
        appid INTEGER
    );
    """)

    # Playtime table
    db.execute("""
    CREATE TABLE IF NOT EXISTS player_hours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        steamid TEXT,
        appid INTEGER,
        hours REAL,
        last_updated TEXT
    );
    """)

    # User ratings + notes
    db.execute("""
    CREATE TABLE IF NOT EXISTS user_game_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        appid INTEGER,
        rating INTEGER,
        notes TEXT,
        play_order INTEGER,
        date_added TEXT
    );
    """)

    db.commit()
    db.close()

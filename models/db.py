import os
import psycopg
from flask import g

DATABASE_URL = os.environ.get("DATABASE_URL")

print("=== DB DEBUG ===")
print("DATABASE_URL:", DATABASE_URL)
print("==============")

# psycopg3 version of get_db
def get_db():
    if 'db' not in g:
        # Make connection return rows as dict-like objects
        g.db = psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Initialization for Postgres tables
def init_db():
    db = get_db()
    cur = db.cursor()

    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        steamid TEXT UNIQUE,
        display_name TEXT,
        avatar_url TEXT,
        is_admin BOOLEAN DEFAULT FALSE
    );
    """)

    # Games metadata
    cur.execute("""
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

    # Owned games
    cur.execute("""
    CREATE TABLE IF NOT EXISTS owned_games (
        id SERIAL PRIMARY KEY,
        steamid TEXT,
        appid INTEGER
    );
    """)

    # Playtime table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS player_hours (
        id SERIAL PRIMARY KEY,
        steamid TEXT,
        appid INTEGER,
        hours REAL,
        last_updated TEXT
    );
    """)

    # User ratings + notes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_game_list (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        appid INTEGER,
        rating INTEGER,
        notes TEXT,
        play_order INTEGER,
        date_added TEXT
    );
    """)

    db.commit()
    cur.close()

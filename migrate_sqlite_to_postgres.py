import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# ---------------------------
# CONFIG
# ---------------------------
SQLITE_PATH = "instance/steamcatalog.db"  # path to your local SQLite DB
POSTGRES_URL = "postgresql://steamfamilydb_user:orUKsUygZZcyP7o6TBDxaYXPDGxHhnjE@dpg-d4j1jefgi27c73eurpu0-a.oregon-postgres.render.com/steamfamilydb"

# ---------------------------
# CONNECT TO DBs
# ---------------------------
sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

pg_conn = psycopg2.connect(POSTGRES_URL, cursor_factory=RealDictCursor)
pg_cur = pg_conn.cursor()

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def safe_int(val):
    """Convert empty string or invalid input to None for integer columns."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

# ---------------------------
# ENSURE TABLES EXIST (Postgres)
# ---------------------------
pg_cur.execute("""
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

pg_cur.execute("""
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

pg_cur.execute("""
CREATE TABLE IF NOT EXISTS owned_games (
    id SERIAL PRIMARY KEY,
    steamid TEXT,
    appid INTEGER
);
""")

pg_cur.execute("""
CREATE TABLE IF NOT EXISTS player_hours (
    id SERIAL PRIMARY KEY,
    steamid TEXT,
    appid INTEGER,
    hours REAL,
    last_updated TEXT
);
""")

pg_cur.execute("""
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

pg_conn.commit()
print("Postgres tables ensured.")

# ---------------------------
# TABLES TO MIGRATE
# ---------------------------
tables = ["users", "games", "owned_games", "player_hours", "user_game_list"]

for table in tables:
    print(f"Migrating table: {table}")
    sqlite_cur.execute(f"SELECT * FROM {table}")
    rows = sqlite_cur.fetchall()
    if not rows:
        print(f"  No rows found for {table}, skipping.")
        continue

    cols = rows[0].keys()
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))

    migrated_count = 0
    for row in rows:
        values = []
        for col in cols:
            val = row[col]
            # Convert empty string to None for integer columns
            if table == "games" and col == "release_year":
                val = safe_int(val)
            # Convert empty string to None for player_hours.hours
            if table == "player_hours" and col == "hours":
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = 0.0
            # Convert empty string to None for user_game_list.rating/play_order
            if table == "user_game_list" and col in ["rating", "play_order"]:
                val = safe_int(val)
            # For users.is_admin, ensure boolean
            if table == "users" and col == "is_admin":
                val = bool(val)
            values.append(val)

        try:
            pg_cur.execute(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                values
            )
            migrated_count += 1
        except Exception as e:
            print(f"  Error inserting into {table}: {e}")
    pg_conn.commit()
    print(f"  Migrated {migrated_count} rows from {table}.")

# ---------------------------
# CLOSE CONNECTIONS
# ---------------------------
sqlite_cur.close()
sqlite_conn.close()
pg_cur.close()
pg_conn.close()
print("Migration complete!")

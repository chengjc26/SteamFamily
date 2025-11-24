from datetime import datetime
from models.db import get_db
from services.steam_api import get_profile, get_owned_games
from services.steam_store import get_store_info

# ========================================================
# NON-STEAM GAMES WITH HARDCODED TITLES
# ========================================================
NON_STEAM_GAMES = {
    900001: "Honkai: Star Rail",
    900002: "Crystal of Atlan",
    900003: "Legends of Runeterra",
    900004: "Nikke: Goddess of Victory",
    900005: "Krunker FRVR",
    900006: "Minecraft",
    900007: "Bloxd.io",
    900008: "Fortnite",
    900009: "League of Legends",
    900010: "Prodigy",
    900011: "Zenless Zone Zero",
    900012: "Valorant",
    900013: "Fall Guys",
    900014: "Genshin Impact",
    900015: "AFK Journey",
    900016: "Roblox",
    900017: "2XKO",
    900018: "Teamfight Tactics",
    900019: "Osu!",
    900020: "Hearthstone"
}



def sync_user(steamid):
    db = get_db()
    print(f"[SYNC] Syncing user {steamid}...")

    # -------------------------
    # 1. Update profile data
    # -------------------------
    profile = get_profile(steamid)
    if profile:
        db.execute("""
            UPDATE users
            SET display_name=?, avatar_url=?
            WHERE steamid=?
        """, (profile["personaname"], profile["avatarfull"], steamid))

    # -------------------------
    # 2. Get owned games
    # -------------------------
    owned = get_owned_games(steamid)
    fresh_appids = {g["appid"] for g in owned}

    existing_rows = db.execute("""
        SELECT appid FROM owned_games WHERE steamid=?
    """, (steamid,)).fetchall()
    existing_appids = {r["appid"] for r in existing_rows}

    new_appids = fresh_appids - existing_appids
    removed_appids = existing_appids - fresh_appids

    # ========================================================
    # FORCE-ADD NON-STEAM GAMES TO OWNED_GAMES
    # ========================================================
    for appid, title in NON_STEAM_GAMES.items():
        db.execute("""
            INSERT OR IGNORE INTO owned_games (steamid, appid)
            VALUES (?, ?)
        """, (steamid, appid))

    # ========================================================
    # ENSURE NON-STEAM GAMES EXIST IN `games` TABLE
    # ========================================================
    for appid, title in NON_STEAM_GAMES.items():
        row = db.execute("SELECT appid FROM games WHERE appid=?", (appid,)).fetchone()
        if not row:
            db.execute("""
                INSERT INTO games (appid, title)
                VALUES (?, ?)
            """, (appid, title))


    # Remove games no longer owned
    for appid in removed_appids:
        db.execute("DELETE FROM owned_games WHERE steamid=? AND appid=?", (steamid, appid))
        db.execute("DELETE FROM player_hours WHERE steamid=? AND appid=?", (steamid, appid))

    # -------------------------
    # 3. Upsert playtime + metadata
    # -------------------------
    for game in owned:
        appid = game["appid"]
        hours = game.get("playtime_forever", 0) / 60

        # Insert into owned_games if new
        if appid in new_appids:
            db.execute("INSERT INTO owned_games (steamid, appid) VALUES (?, ?)", (steamid, appid))

        # Update or insert hours
        existing_hours = db.execute("""
            SELECT id FROM player_hours WHERE steamid=? AND appid=?
        """, (steamid, appid)).fetchone()

        if existing_hours:
            db.execute("""
                UPDATE player_hours
                SET hours=?, last_updated=?
                WHERE steamid=? AND appid=?
            """, (hours, datetime.utcnow().isoformat(), steamid, appid))
        else:
            db.execute("""
                INSERT INTO player_hours (steamid, appid, hours, last_updated)
                VALUES (?, ?, ?, ?)
            """, (steamid, appid, hours, datetime.utcnow().isoformat()))

        # ---------------------------------------------
        # SKIP METADATA if already stored (big speedup)
        # ---------------------------------------------
        existing_meta = db.execute(
            "SELECT appid FROM games WHERE appid=?", (appid,)
        ).fetchone()

        if existing_meta:
            continue  # Skip slow metadata fetch

        # Otherwise fetch metadata with timeout (safe)
        print(f"[META] Fetching store data for appid {appid}...")
        meta = get_store_info(appid)

        if meta:
            db.execute("""
                INSERT INTO games (appid, title, cover_url, description, genres, release_year)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                appid,
                meta["title"],
                meta["cover_url"],
                meta["description"],
                meta["genres"],
                meta["release_year"]
            ))
        else:
            # Fallback minimum entry
            db.execute("""
                INSERT INTO games (appid, title)
                VALUES (?, ?)
            """, (appid, game.get("name", "Unknown Game")))

    db.commit()
    print("[SYNC] Done!")

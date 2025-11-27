from datetime import datetime, timezone
from models.db import get_db
from services.steam_api import get_profile, get_owned_games

NON_STEAM_GAMES = {
    900001: "Honkai: Star Rail",
    900002: "Crystal of Atlan",
    900003: "Legends of Runeterra",
    900004: "Nikke: Goddess of Victory",
    900006: "Minecraft",
    900007: "Bloxd.io",
    900008: "Fortnite",
    900009: "League of Legends",
    900010: "Prodigy",
    900011: "Zenless Zone Zero",
    900012: "Valorant",
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
    # 1. Update profile
    # -------------------------
    profile = get_profile(steamid)
    if profile:
        db.execute("""
            UPDATE users
            SET display_name = %s, avatar_url = %s
            WHERE steamid = %s
        """, (profile["personaname"], profile["avatarfull"], steamid))

    # -------------------------
    # 2. Insert Non-Steam Games
    # -------------------------
    for appid, title in NON_STEAM_GAMES.items():
        db.execute("""
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (steamid, appid))

        db.execute("""
            INSERT INTO games (appid, title)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (appid, title))

    db.commit()

    # -------------------------
    # 3. Get Steam library
    # -------------------------
    owned = get_owned_games(steamid)
    steam_appids = {g["appid"] for g in owned}

    # Get all games user currently owns
    cur = db.execute("SELECT appid FROM owned_games WHERE steamid=%s", (steamid,))
    existing_appids = {row["appid"] for row in cur.fetchall() or []}

    # -------------------------
    # ❌ 4. NO MORE DELETION
    # Manual games remain forever
    # -------------------------

    # -------------------------
    # 5. Sync hours + add new games
    # -------------------------
    for game in owned:
        appid = game["appid"]

        # Non-steam skip
        if appid in NON_STEAM_GAMES:
            continue

        hours = game.get("playtime_forever", 0) / 60
        timestamp = datetime.now(timezone.utc).isoformat()

        # Ensure user owns the game
        db.execute("""
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (steamid, appid))

        # Minimal metadata
        db.execute("""
            INSERT INTO games (appid, title)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (appid, game.get("name", None)))

        # Sync hours
        cur = db.execute("""
            SELECT id FROM player_hours
            WHERE steamid=%s AND appid=%s
        """, (steamid, appid))

        if cur.fetchone():
            db.execute("""
                UPDATE player_hours
                SET hours=%s, last_updated=%s
                WHERE steamid=%s AND appid=%s
            """, (hours, timestamp, steamid, appid))
        else:
            db.execute("""
                INSERT INTO player_hours (steamid, appid, hours, last_updated)
                VALUES (%s, %s, %s, %s)
            """, (steamid, appid, hours, timestamp))

    db.commit()
    print("[SYNC] ✔ Manual games preserved!")

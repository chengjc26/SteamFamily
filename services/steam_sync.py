from datetime import datetime, timezone
from models.db import get_db
from services.steam_api import get_profile, get_owned_games

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
    # 1. Update profile (fast)
    # -------------------------
    profile = get_profile(steamid)
    if profile:
        db.execute(
            """
            UPDATE users
            SET display_name = %s, avatar_url = %s
            WHERE steamid = %s
            """,
            (profile["personaname"], profile["avatarfull"], steamid)
        )

    # -------------------------
    # 2. Insert Non-Steam Games (fast)
    # -------------------------
    for appid, title in NON_STEAM_GAMES.items():
        db.execute(
            """
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (steamid, appid)
        )

        # Insert minimal metadata (appid + title)
        db.execute(
            """
            INSERT INTO games (appid, title)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (appid, title)
        )

    db.commit()

    # -------------------------
    # 3. Get steam library (fast)
    # -------------------------
    owned = get_owned_games(steamid)
    fresh_appids = {g["appid"] for g in owned}

    cur = db.execute(
        "SELECT appid FROM owned_games WHERE steamid=%s",
        (steamid,)
    )
    existing_rows = cur.fetchall() or []
    existing_appids = {row["appid"] for row in existing_rows}

    # Games removed from Steam (ignore non-steam)
    removed_appids = {
        appid for appid in (existing_appids - fresh_appids)
        if appid not in NON_STEAM_GAMES
    }

    for appid in removed_appids:
        db.execute(
            "DELETE FROM owned_games WHERE steamid=%s AND appid=%s",
            (steamid, appid)
        )
        db.execute(
            "DELETE FROM player_hours WHERE steamid=%s AND appid=%s",
            (steamid, appid)
        )

    # -------------------------
    # 4. Sync hours + add new games (SUPER FAST)
    # -------------------------
    for game in owned:
        appid = game["appid"]

        if appid in NON_STEAM_GAMES:
            continue

        hours = game.get("playtime_forever", 0) / 60
        timestamp = datetime.now(timezone.utc).isoformat()

        # Add ownership
        db.execute(
            """
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (steamid, appid)
        )

        # Ensure game entry exists minimally (appid + title)
        cur = db.execute(
            "SELECT appid FROM games WHERE appid=%s",
            (appid,)
        )
        exists_meta = cur.fetchone()

        if not exists_meta:
            db.execute(
                """
                INSERT INTO games (appid, title)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (appid, game.get("name", None))
            )

        # Check if hours already exist
        cur = db.execute(
            """
            SELECT id FROM player_hours
            WHERE steamid=%s AND appid=%s
            """,
            (steamid, appid)
        )
        exists_hours = cur.fetchone()

        if exists_hours:
            db.execute(
                """
                UPDATE player_hours
                SET hours=%s, last_updated=%s
                WHERE steamid=%s AND appid=%s
                """,
                (hours, timestamp, steamid, appid)
            )
        else:
            db.execute(
                """
                INSERT INTO player_hours (steamid, appid, hours, last_updated)
                VALUES (%s, %s, %s, %s)
                """,
                (steamid, appid, hours, timestamp)
            )

    db.commit()
    print("[SYNC] ✔ Potato mode finished!")

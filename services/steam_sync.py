from datetime import datetime, timezone
from models.db import get_db
from services.steam_api import get_profile, get_owned_games
from services.steam_store import (
    get_store_info,
    get_steamspy_tags,
    get_sgdb_vertical_cover,
    get_sgdb_poster,
    get_steam_vertical_cover
)

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
    # 1. Update profile
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
    # 2. Insert Non-Steam Games (once)
    # -------------------------
    for appid, title in NON_STEAM_GAMES.items():
        db.execute(
            """
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (steamid, appid),
        )

        db.execute(
            """
            INSERT INTO games (appid, title)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (appid, title),
        )

    db.commit()

    # -------------------------
    # 3. Get Steam library
    # -------------------------
    owned = get_owned_games(steamid)
    fresh_appids = {g["appid"] for g in owned}

    cur = db.execute(
        "SELECT appid FROM owned_games WHERE steamid=%s",
        (steamid,)
    )
    existing_rows = cur.fetchall() or []
    existing_appids = {row["appid"] for row in existing_rows}

    # -------------------------
    # 4. Removed Steam games
    # -------------------------
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
    # 5. Sync Steam games + hours + metadata
    # -------------------------
    for game in owned:
        appid = game["appid"]

        if appid in NON_STEAM_GAMES:
            continue

        hours = game.get("playtime_forever", 0) / 60
        timestamp = datetime.now(timezone.utc).isoformat()

        # Insert ownership
        db.execute(
            """
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (steamid, appid)
        )

        # Check if hours exist
        cur = db.execute(
            """
            SELECT id FROM player_hours
            WHERE steamid=%s AND appid=%s
            """,
            (steamid, appid)
        )
        exists = cur.fetchone()

        if exists:
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

        # Metadata check
        cur = db.execute(
            "SELECT appid FROM games WHERE appid=%s",
            (appid,)
        )
        row_meta = cur.fetchone()

        if row_meta:
            continue

        print(f"[META] Fetching metadata for {appid}...")

        meta = get_store_info(appid)
        tags = get_steamspy_tags(appid)
        tag_string = ",".join(tags) if tags else None

        cover_sgdb_portrait = get_sgdb_vertical_cover(appid)
        cover_sgdb_poster = get_sgdb_poster(appid)
        cover_steam_vertical = get_steam_vertical_cover(appid)
        fallback = meta.get("fallback_cover") if meta else None

        best_cover = (
            cover_sgdb_portrait or
            cover_sgdb_poster or
            cover_steam_vertical or
            fallback
        )

        db.execute(
            """
            INSERT INTO games (appid, title, cover_url, description, genres, release_year, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (appid) DO NOTHING
            """,
            (
                appid,
                meta.get("title") if meta else None,
                best_cover,
                meta.get("description") if meta else None,
                meta.get("genres") if meta else None,
                meta.get("release_year") if meta else None,
                tag_string,
            )
        )

    db.commit()
    print("[SYNC] Done!")

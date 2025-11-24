from datetime import datetime
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
    # Update profile
    # -------------------------
    profile = get_profile(steamid)
    if profile:
        db.execute("""
            UPDATE users
            SET display_name=?, avatar_url=?
            WHERE steamid=?
        """, (profile["personaname"], profile["avatarfull"], steamid))

    # -------------------------
    # Insert Non-Steam Games FIRST (never touched again)
    # -------------------------
    for appid, title in NON_STEAM_GAMES.items():
        db.execute("INSERT OR IGNORE INTO owned_games (steamid, appid) VALUES (?,?)",
                   (steamid, appid))
        db.execute("INSERT OR IGNORE INTO games (appid, title) VALUES (?,?)",
                   (appid, title))

    # 🔥 commit now
    db.commit()

    # -------------------------
    # Get Steam owned games
    # -------------------------
    owned = get_owned_games(steamid)
    fresh_appids = {g["appid"] for g in owned}

    existing_rows = db.execute(
        "SELECT appid FROM owned_games WHERE steamid=?",
        (steamid,)
    ).fetchall()
    existing_appids = {r["appid"] for r in existing_rows}

    new_appids = fresh_appids - existing_appids

    # -------------------------
    # Removed games
    # -------------------------
    removed_appids = {
        appid for appid in (existing_appids - fresh_appids)
        if appid not in NON_STEAM_GAMES
    }

    # delete removed
    for appid in removed_appids:
        db.execute("DELETE FROM owned_games WHERE steamid=? AND appid=?", (steamid, appid))
        db.execute("DELETE FROM player_hours WHERE steamid=? AND appid=?", (steamid, appid))

    # -------------------------
    # Sync Steam games
    # -------------------------
    for game in owned:
        appid = game["appid"]

        if appid in NON_STEAM_GAMES:
            continue

        hours = game.get("playtime_forever", 0) / 60

        if appid in new_appids:
            db.execute("INSERT OR IGNORE INTO owned_games (steamid, appid) VALUES (?,?)",
                       (steamid, appid))

        row = db.execute("""
            SELECT id FROM player_hours
            WHERE steamid=? AND appid=?
        """, (steamid, appid)).fetchone()

        if row:
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

        row_meta = db.execute("""
            SELECT title, tags, cover_url, description
            FROM games
            WHERE appid=?
        """, (appid,)).fetchone()

        if row_meta and (
            row_meta["cover_url"] is not None or
            row_meta["tags"] is not None or
            row_meta["description"] is not None
        ):
            continue

        print(f"[META] Fetching metadata for {appid}...")

        meta = get_store_info(appid)
        tags = get_steamspy_tags(appid)
        tag_string = ",".join(tags) if tags else None

        cover_sgdb_portrait = get_sgdb_vertical_cover(appid)
        cover_sgdb_poster = get_sgdb_poster(appid)
        cover_steam_vertical = get_steam_vertical_cover(appid)
        cover_horizontal = meta.get("fallback_cover") if meta else None

        best_cover = (
            cover_sgdb_portrait or
            cover_sgdb_poster or
            cover_steam_vertical or
            cover_horizontal
        )

        db.execute("""
            UPDATE games
            SET
                title        = COALESCE(?, title),
                cover_url    = COALESCE(?, cover_url),
                description  = COALESCE(?, description),
                genres       = COALESCE(?, genres),
                release_year = COALESCE(?, release_year),
                tags         = COALESCE(?, tags)
            WHERE appid = ?
        """, (
            meta.get("title") if meta else None,
            best_cover,
            meta.get("description") if meta else None,
            meta.get("genres") if meta else None,
            meta.get("release_year") if meta else None,
            tag_string,
            appid
        ))

    db.commit()
    print("[SYNC] Done!")

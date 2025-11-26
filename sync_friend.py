import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests

# ============================================================
# CONFIG — YOUR RENDER DATABASE
# ============================================================
DATABASE_URL = "postgresql://steamfamilydb_user:orUKsUygZZcyP7o6TBDxaYXPDGxHhnjE@dpg-d4j1jefgi27c73eurpu0-a.oregon-postgres.render.com/steamfamilydb"

STEAM_API_KEY = "E4981054BC0ABE9091F094B51D4E39A2"
FRIEND_STEAMID = "76561198411897137"


# ============================================================
# STEAM API HELPERS
# ============================================================
def get_profile(steamid):
    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={steamid}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    players = r.json().get("response", {}).get("players", [])
    return players[0] if players else None


def get_owned_games(steamid):
    url = (
        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={STEAM_API_KEY}&steamid={steamid}&include_appinfo=1&include_played_free_games=1"
    )
    r = requests.get(url)
    if r.status_code != 200:
        return []
    return r.json().get("response", {}).get("games", [])


# ============================================================
# NON-STEAM GAMES (your custom list)
# ============================================================
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
    900020: "Hearthstone",
}


# ============================================================
# SYNC FUNCTION
# ============================================================
def sync_user(steamid):
    conn = psycopg2.connect(DATABASE_URL)
    db = conn.cursor(cursor_factory=RealDictCursor)

    print(f"[SYNC] Syncing {steamid}...")

    # ------------------------------------------
    # UPDATE PROFILE
    # ------------------------------------------
    profile = get_profile(steamid)
    if profile:
        db.execute(
            """
            UPDATE users
            SET display_name=%s, avatar_url=%s
            WHERE steamid=%s
            """,
            (profile["personaname"], profile["avatarfull"], steamid),
        )

    # ------------------------------------------
    # INSERT NON-STEAM GAMES
    # ------------------------------------------
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

    conn.commit()

    # ------------------------------------------
    # GET STEAM LIBRARY
    # ------------------------------------------
    owned = get_owned_games(steamid)
    steam_appids = {g["appid"] for g in owned}

    # GET EXISTING APPIDS
    db.execute(
        "SELECT appid FROM owned_games WHERE steamid=%s",
        (steamid,),
    )
    existing_rows = db.fetchall() or []
    existing_appids = {row["appid"] for row in existing_rows}

    # REMOVED GAMES (not non-steam)
    removed = (existing_appids - steam_appids) - set(NON_STEAM_GAMES.keys())
    for appid in removed:
        db.execute(
            "DELETE FROM owned_games WHERE steamid=%s AND appid=%s",
            (steamid, appid),
        )
        db.execute(
            "DELETE FROM player_hours WHERE steamid=%s AND appid=%s",
            (steamid, appid),
        )

    # ------------------------------------------
    # SYNC HOURS + METADATA
    # ------------------------------------------
    for game in owned:
        appid = game["appid"]
        if appid in NON_STEAM_GAMES:
            continue

        hours = game.get("playtime_forever", 0) / 60

        # INSERT OWNERSHIP
        db.execute(
            """
            INSERT INTO owned_games (steamid, appid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (steamid, appid),
        )

        # INSERT or UPDATE HOURS
        db.execute(
            """
            SELECT id FROM player_hours
            WHERE steamid=%s AND appid=%s
            """,
            (steamid, appid),
        )
        row = db.fetchone()

        if row:
            db.execute(
                """
                UPDATE player_hours
                SET hours=%s, last_updated=%s
                WHERE steamid=%s AND appid=%s
                """,
                (hours, datetime.utcnow().isoformat(), steamid, appid),
            )
        else:
            db.execute(
                """
                INSERT INTO player_hours (steamid, appid, hours, last_updated)
                VALUES (%s, %s, %s, %s)
                """,
                (steamid, appid, hours, datetime.utcnow().isoformat()),
            )

    conn.commit()
    conn.close()

    print(f"[SYNC] ✔ Finished syncing {steamid}")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    sync_user(FRIEND_STEAMID)

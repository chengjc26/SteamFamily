import requests

SGDB_API_KEY = "d95ccb48b2d2d61b46e582dd37f5b084"
SGDB_HEADERS = {
    "Authorization": f"Bearer {SGDB_API_KEY}",
    "User-Agent": "SteamFamilyApp/1.0"
}

# ============================================================
# 1) SGDB PORTRAIT (Top-tier vertical art, rare)
# ============================================================
def get_sgdb_vertical_cover(appid):
    try:
        url = f"https://www.steamgriddb.com/api/v2/grids/steam/{appid}?types=portrait&dimensions=600x900"
        r = requests.get(url, headers=SGDB_HEADERS, timeout=4)

        if r.status_code != 200:
            return None

        data = r.json().get("data", [])
        if not data:
            return None

        return data[0]["url"]

    except:
        return None


# ============================================================
# 2) SGDB POSTER (Most games have posters — vertical!)
# ============================================================
def get_sgdb_poster(appid):
    try:
        url = f"https://www.steamgriddb.com/api/v2/grids/steam/{appid}?types=poster&dimensions=600x900"
        r = requests.get(url, headers=SGDB_HEADERS, timeout=4)

        if r.status_code != 200:
            return None

        data = r.json().get("data", [])
        if not data:
            return None

        return data[0]["url"]

    except:
        return None


# ============================================================
# 3) Steam official vertical: library_600x900.jpg
# ============================================================
def get_steam_vertical_cover(appid):
    """
    Steam's guaranteed vertical library cover.
    Does not require API, image exists for ~99% of games.
    """
    return f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900.jpg"


# ============================================================
# 4) Steam Store metadata (horizontal fallback)
# ============================================================
def get_store_info(appid):
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en"
        data = requests.get(url, timeout=4).json()

        if not data or not data[str(appid)]["success"]:
            return None

        game = data[str(appid)]["data"]

        # Horizontal images (fallback only)
        fallback_cover = (
            game.get("capsule_imagev5") or
            game.get("capsule_image") or
            game.get("header_image")
        )

        return {
            "title": game.get("name"),
            "description": game.get("short_description", ""),
            "release_year": game.get("release_date", {}).get("date", "")[-4:],
            "genres": ", ".join(g["description"] for g in game.get("genres", [])),
            "fallback_cover": fallback_cover
        }

    except:
        return None


# ============================================================
# 5) SteamSpy tags
# ============================================================
def get_steamspy_tags(appid):
    try:
        url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
        data = requests.get(url, timeout=4).json()

        if "tags" not in data or not data["tags"]:
            return []

        sorted_tags = sorted(
            data["tags"].items(), key=lambda x: x[1], reverse=True
        )

        return [tag for tag, score in sorted_tags[:10]]

    except:
        return []

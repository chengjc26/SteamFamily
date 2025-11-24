import requests

STORE_API = "https://store.steampowered.com/api/appdetails"

def get_store_info(appid):
    try:
        url = f"{STORE_API}?appids={appid}&l=en&cc=us"
        response = requests.get(url, timeout=5)
        data = response.json()

        # Bad or missing store data
        if not data or not data.get(str(appid), {}).get("success"):
            return {}

        info = data[str(appid)]["data"]

        return {
            "title": info.get("name"),
            "description": info.get("short_description", ""),
            "cover_url": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900_2x.jpg",
            "genres": ", ".join([g["description"] for g in info.get("genres", [])])
                        if info.get("genres") else "",
            "release_year": info.get("release_date", {}).get("date", "")
        }

    except Exception as e:
        print(f"[STORE ERROR] AppID {appid}: {e}")
        return {}

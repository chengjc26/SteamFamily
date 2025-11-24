import os
import requests

API_KEY = os.environ.get("STEAM_API_KEY")

BASE_USER = "https://api.steampowered.com/ISteamUser"
BASE_PLAYER = "https://api.steampowered.com/IPlayerService"


def get_profile(steamid):
    url = f"{BASE_USER}/GetPlayerSummaries/v2/?key={API_KEY}&steamids={steamid}"
    data = requests.get(url).json()
    try:
        return data["response"]["players"][0]
    except:
        return None


def get_owned_games(steamid):
    url = (
        f"{BASE_PLAYER}/GetOwnedGames/v1/"
        f"?key={API_KEY}"
        f"&steamid={steamid}"
        f"&include_appinfo=1"
        f"&include_played_free_games=1"
        f"&include_free_sub=1"
        f"&include_unvetted_apps=1"
    )

    data = requests.get(url).json()
    return data.get("response", {}).get("games", [])

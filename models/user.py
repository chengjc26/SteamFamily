from flask_login import UserMixin
from models.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests

class User(UserMixin):

    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.password_hash = row["password_hash"]
        self.steamid = row["steamid"]
        self.display_name = row["display_name"]
        self.avatar_url = row["avatar_url"]

    @staticmethod
    def create(username, password, steamid):
        db = get_db()

        # Hash password
        pw_hash = generate_password_hash(password)

        # Fetch profile safely
        profile = User.fetch_steam_profile(steamid)

        db.execute("""
            INSERT INTO users (username, password_hash, steamid, display_name, avatar_url)
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            pw_hash,
            steamid,
            profile.get("personaname"),
            profile.get("avatarfull")
        ))

        db.commit()

    @staticmethod
    def fetch_steam_profile(steamid):
        API_KEY = os.environ.get("STEAM_API_KEY")
        url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={API_KEY}&steamids={steamid}"
        r = requests.get(url)

        # If Steam API fails
        if r.status_code != 200:
            return {"personaname": None, "avatarfull": None}

        data = r.json()

        players = data.get("response", {}).get("players", [])

        # Invalid or private steamid = empty fields
        if not players:
            return {"personaname": None, "avatarfull": None}

        p = players[0]
        return {
            "personaname": p.get("personaname"),
            "avatarfull": p.get("avatarfull")
        }

    @staticmethod
    def get_by_username(username):
        row = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if row:
            return User(row)
        return None

    @staticmethod
    def get_by_id(user_id):
        row = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row:
            return User(row)
        return None

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

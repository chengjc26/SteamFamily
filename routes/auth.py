from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ---------------------------------------------
# LOGIN — no auto-sync
# ---------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.get_by_username(username)

        if user and user.verify_password(password):
            login_user(user)
            return redirect("/")

        flash("Invalid username or password")

    return render_template("login.html")


# ---------------------------------------------
# REGISTER — no auto-sync
# ---------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        steamid = request.form["steamid"].strip()

        # -----------------------------
        # 1. Username duplicate check
        # -----------------------------
        if User.get_by_username(username):
            flash("Username already exists")
            return redirect(url_for("auth.register"))

        # -----------------------------
        # 2. SteamID format validation
        # -----------------------------
        if not steamid.isdigit() or len(steamid) != 17:
            flash("Invalid SteamID64. It must be exactly 17 digits.")
            return redirect(url_for("auth.register"))

        # -----------------------------
        # 3. SteamID duplicate check
        # -----------------------------
        db = get_db()
        existing = db.execute(
            "SELECT 1 FROM users WHERE steamid = ?", (steamid,)
        ).fetchone()

        if existing:
            flash("This SteamID64 is already registered.")
            return redirect(url_for("auth.register"))

        # -----------------------------
        # 4. Validate Steam profile exists
        # -----------------------------
        profile = User.fetch_steam_profile(steamid)

        if not profile.get("personaname"):
            flash("This SteamID64 does not correspond to a valid Steam account.")
            return redirect(url_for("auth.register"))

        # -----------------------------
        # 5. Create user
        # -----------------------------
        User.create(username, password, steamid)

        flash("Account created successfully! Please log in.")
        return redirect(url_for("auth.login"))

    return render_template("register.html")



# ---------------------------------------------
# LOGOUT
# ---------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

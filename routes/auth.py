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
        username = request.form["username"]
        password = request.form["password"]
        steamid = request.form["steamid"]

        if User.get_by_username(username):
            flash("Username already exists")
            return redirect(url_for("auth.register"))

        User.create(username, password, steamid)
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

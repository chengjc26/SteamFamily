from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models.db import get_db
from datetime import datetime

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

# --------------------------------------------------
# PROFILE PAGE
# --------------------------------------------------
@profile_bp.route("/")
@login_required
def profile():
    db = get_db()

    steamid = current_user.steamid

    # Total hours
    hours_row = db.execute("""
        SELECT COALESCE(SUM(hours), 0) AS total
        FROM player_hours
        WHERE steamid = %s
    """, (steamid,)).fetchone()

    total_hours = hours_row["total"]

    # Ratings
    rating_rows = db.execute("""
        SELECT rating FROM user_game_list WHERE user_id = %s
    """, (current_user.id,)).fetchall()

    ratings = [r["rating"] for r in rating_rows]
    avg_rating = sum(ratings)/len(ratings) if ratings else None
    rated_count = len(ratings)

    # Recently rated games
    recent_rows = db.execute("""
        SELECT g.appid, g.title, g.cover_url, u.rating
        FROM user_game_list u
        JOIN games g ON g.appid = u.appid
        WHERE u.user_id = %s
        ORDER BY u.date_added DESC
        LIMIT 12
    """, (current_user.id,)).fetchall()

    return render_template(
        "profile.html",
        user=current_user,
        total_hours=total_hours,
        avg_rating=avg_rating,
        rated_count=rated_count,
        recent=recent_rows
    )

# --------------------------------------------------
# SAVE RATING / NOTES / PLAY ORDER
# --------------------------------------------------
@profile_bp.route("/edit/<int:appid>", methods=["POST"])
@login_required
def edit_game(appid):
    db = get_db()

    rating = request.form.get("rating")
    notes = request.form.get("notes")
    play_order = request.form.get("play_order")

    existing = db.execute("""
        SELECT id FROM user_game_list
        WHERE user_id = %s AND appid = %s
    """, (current_user.id, appid)).fetchone()

    if existing:
        # Update existing entry
        db.execute("""
            UPDATE user_game_list
            SET rating=%s, notes=%s, play_order=%s
            WHERE user_id=%s AND appid=%s
        """, (rating, notes, play_order, current_user.id, appid))

    else:
        # Insert new entry
        db.execute("""
            INSERT INTO user_game_list (user_id, appid, rating, notes, play_order, date_added)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            current_user.id, appid, rating, notes, play_order,
            datetime.utcnow().isoformat()
        ))

    db.commit()
    return redirect(url_for("catalog.game_detail", appid=appid))

# --------------------------------------------------
# USER-ACCESSIBLE STEAM SYNC (current user only)
# --------------------------------------------------
from services.steam_sync import sync_user
from flask import request

@profile_bp.route("/sync")
@login_required
def sync_user_route():
    sync_user(current_user.steamid)  # Sync ONLY this user
    flash("Steam sync completed.", "success")
    return redirect(request.referrer or url_for("profile.profile"))

from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from models.db import get_db
from datetime import datetime

family_rate_bp = Blueprint("family_rate", __name__, url_prefix="/family")

@family_rate_bp.route("/rate/<int:appid>", methods=["POST"])
@login_required
def rate_game(appid):
    db = get_db()
    rating = request.json.get("rating")

    # Check if an entry already exists
    exists = db.execute("""
        SELECT id FROM user_game_list
        WHERE user_id=? AND appid=?
    """, (current_user.id, appid)).fetchone()

    if exists:
        # Update existing row
        db.execute("""
            UPDATE user_game_list
            SET rating=?, date_added=?
            WHERE user_id=? AND appid=?
        """, (rating, datetime.utcnow().isoformat(), current_user.id, appid))

    else:
        # Insert NEW row with all required fields
        db.execute("""
            INSERT INTO user_game_list (user_id, appid, rating, notes, play_order, date_added)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            current_user.id,
            appid,
            rating,
            "",                # notes empty by default
            None,              # play_order default null
            datetime.utcnow().isoformat()
        ))

    db.commit()
    return jsonify(success=True)

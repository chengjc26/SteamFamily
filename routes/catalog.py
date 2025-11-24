from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user, login_required
from models.db import get_db

catalog_bp = Blueprint("catalog", __name__, url_prefix="/")

# ============================================================
#                     GAME LIST
# ============================================================
@catalog_bp.route("/games")
@login_required
def games():
    db = get_db()

    rows = db.execute("""
        SELECT 
            g.appid,
            g.title,
            COALESCE(g.custom_cover_url, g.cover_url) AS cover_url,
            COALESCE(ph.hours, 0) AS hours,  -- FINAL HOURS (ONLY SOURCE)
            ug.rating AS user_rating
        FROM owned_games og
        JOIN games g ON og.appid = g.appid
        LEFT JOIN player_hours ph 
            ON ph.appid = g.appid AND ph.steamid = og.steamid
        LEFT JOIN user_game_list ug
            ON ug.appid = g.appid AND ug.user_id = ?
        WHERE og.steamid = ?
        ORDER BY g.title COLLATE NOCASE ASC
    """, (current_user.id, current_user.steamid)).fetchall()

    return render_template("games.html", games=rows)


# ============================================================
#                     GAME DETAIL PAGE
# ============================================================
@catalog_bp.route("/game/<int:appid>")
@login_required
def game_detail(appid):
    db = get_db()

    # Game base data
    game = db.execute("""
        SELECT
            appid, title, description,
            COALESCE(custom_cover_url, cover_url) AS cover_url
        FROM games
        WHERE appid=?
    """, (appid,)).fetchone()

    # Hours (only source)
    hours_row = db.execute("""
        SELECT hours
        FROM player_hours
        WHERE steamid=? AND appid=?
    """, (current_user.steamid, appid)).fetchone()

    final_hours = hours_row["hours"] if hours_row else 0

    # User-specific rating + notes
    user_game = db.execute("""
        SELECT rating, notes, play_order
        FROM user_game_list
        WHERE user_id=? AND appid=?
    """, (current_user.id, appid)).fetchone()

    return render_template(
        "game_detail.html",
        game=game,
        hours=final_hours,
        user_rating=user_game["rating"] if user_game else None,
        user_notes=user_game["notes"] if user_game else "",
        user_game=user_game
    )


# ============================================================
#                     SAVE RATING + NOTES
# ============================================================
@catalog_bp.route("/game/<int:appid>/save_entry", methods=["POST"])
@login_required
def save_entry(appid):
    db = get_db()

    rating_text = request.form.get("rating", "").strip()
    notes = request.form.get("notes", "")

    # convert rating text → int
    try:
        rating_value = int(rating_text)
        if rating_value < 1: rating_value = 1
        if rating_value > 10: rating_value = 10
    except:
        rating_value = None

    # ensure row exists
    # Try to update existing row
    db.execute("""
        UPDATE user_game_list
        SET rating=?, notes=?
        WHERE user_id=? AND appid=?
    """, (rating_value, notes, current_user.id, appid))

    # If no row was updated, insert fresh
    if db.total_changes == 0:
        db.execute("""
            INSERT INTO user_game_list (user_id, appid, rating, notes)
            VALUES (?, ?, ?, ?)
        """, (current_user.id, appid, rating_value, notes))


    # update with CLEAN value
    db.execute("""
        UPDATE user_game_list
        SET rating=?, notes=?
        WHERE user_id=? AND appid=?
    """, (rating_value, notes, current_user.id, appid))

    db.commit()
    return redirect(url_for("catalog.game_detail", appid=appid))



# ============================================================
#                     UPDATE MANUAL HOURS
# ============================================================
@catalog_bp.route("/game/<int:appid>/update_hours", methods=["POST"])
@login_required
def update_hours(appid):
    db = get_db()

    hours_text = request.form.get("hours", "").strip()

    # convert hours text → float
    try:
        hours_value = float(hours_text)
    except:
        hours_value = 0.0

    # ensure row exists
    # Try update
    db.execute("""
        UPDATE player_hours
        SET hours = ?
        WHERE steamid = ? AND appid = ?
    """, (hours_value, current_user.steamid, appid))

    # If no row updated → insert
    if db.total_changes == 0:
        db.execute("""
            INSERT INTO player_hours (steamid, appid, hours)
            VALUES (?, ?, ?)
        """, (current_user.steamid, appid, hours_value))


    # update with CLEAN value
    db.execute("""
        UPDATE player_hours
        SET hours = ?
        WHERE steamid=? AND appid=?
    """, (hours_value, current_user.steamid, appid))

    db.commit()
    return redirect(url_for("catalog.game_detail", appid=appid))



# ============================================================
#                     COVER CUSTOMIZATION
# ============================================================
@catalog_bp.route("/game/<int:appid>/set_cover", methods=["POST"])
@login_required
def set_custom_cover(appid):
    db = get_db()
    url = request.form.get("cover_url")

    db.execute("""
        UPDATE games
        SET custom_cover_url = ?
        WHERE appid = ?
    """, (url, appid))
    db.commit()

    return redirect(url_for("catalog.game_detail", appid=appid))


@catalog_bp.route("/game/<int:appid>/reset_cover", methods=["POST"])
@login_required
def reset_custom_cover(appid):
    db = get_db()

    db.execute("""
        UPDATE games
        SET custom_cover_url = NULL
        WHERE appid = ?
    """, (appid,))
    db.commit()

    return redirect(url_for("catalog.game_detail", appid=appid))


# ============================================================
#                     FAMILY PAGE
# ============================================================
@catalog_bp.route("/family")
@login_required
def family():
    db = get_db()

    games_raw = db.execute("""
        SELECT 
            g.appid,
            g.title,
            COALESCE(g.custom_cover_url, g.cover_url) AS cover_url,
            COUNT(DISTINCT og.steamid) AS owner_count
        FROM owned_games og
        JOIN games g ON g.appid = og.appid
        GROUP BY g.appid
        ORDER BY g.title ASC
    """).fetchall()

    games = []

    for row in games_raw:
        appid = row["appid"]

        member_rows = db.execute("""
            SELECT 
                u.id AS user_id,
                u.display_name,
                u.avatar_url,
                COALESCE(ph.hours, 0) AS hours,
                CASE WHEN og2.steamid IS NOT NULL THEN 1 ELSE 0 END AS owns,
                u.steamid
            FROM users u
            LEFT JOIN player_hours ph 
                ON ph.steamid = u.steamid AND ph.appid = ?
            LEFT JOIN owned_games og2 
                ON og2.steamid = u.steamid AND og2.appid = ?
            ORDER BY u.display_name ASC
        """, (appid, appid)).fetchall()

        members = []

        for m in member_rows:
            rating_row = db.execute("""
                SELECT rating, notes
                FROM user_game_list
                WHERE user_id=(SELECT id FROM users WHERE steamid=?) AND appid=?
            """, (m["steamid"], appid)).fetchone()

            members.append({
                "user_id": m["user_id"],
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "hours": m["hours"],
                "owns": m["owns"],
                "rating": rating_row["rating"] if rating_row else None,
                "notes": rating_row["notes"] if rating_row else "",
            })

        games.append({
            "appid": appid,
            "title": row["title"],
            "cover_url": row["cover_url"],
            "members": members
        })

    return render_template("family.html", games=games)


# ============================================================
#                     STATS PAGE
# ============================================================
@catalog_bp.route("/stats")
@login_required
def stats():
    db = get_db()
    steamid = current_user.steamid

    # Total Hours
    total_hours_row = db.execute("""
        SELECT IFNULL(SUM(hours), 0) AS total
        FROM player_hours
        WHERE steamid=?
    """, (steamid,)).fetchone()
    total_hours = total_hours_row["total"]

    # Ratings
    rating_rows = db.execute("""
        SELECT rating FROM user_game_list WHERE user_id = ?
    """, (current_user.id,)).fetchall()

    ratings = [r["rating"] for r in rating_rows]
    avg_rating = sum(ratings) / len(ratings) if ratings else None

    # Top Games
    top_rows = db.execute("""
        SELECT 
            g.title, 
            COALESCE(g.custom_cover_url, g.cover_url) AS cover_url, 
            SUM(ph.hours) AS hours
        FROM games g
        JOIN player_hours ph ON g.appid = ph.appid
        WHERE ph.steamid = ?
        GROUP BY g.title, cover_url
        ORDER BY hours DESC
        LIMIT 10
    """, (steamid,)).fetchall()

    # Games per genre
    genre_count = {}
    rows = db.execute("""
        SELECT g.genres
        FROM games g
        JOIN owned_games og ON og.appid = g.appid
        WHERE og.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        if row["genres"]:
            for genre in [g.strip() for g in row["genres"].split(",")]:
                genre_count[genre] = genre_count.get(genre, 0) + 1

    sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
    top_10 = sorted_genres[:10]
    if len(sorted_genres) > 10:
        others_total = sum(x[1] for x in sorted_genres[10:])
        top_10.append(("Others", others_total))

    genre_labels = [g for g, _ in top_10]
    genre_data = [c for _, c in top_10]

    # Hours by genre
    hours_by_genre = {}
    rows = db.execute("""
        SELECT g.genres, ph.hours
        FROM games g
        JOIN player_hours ph ON g.appid = ph.appid
        WHERE ph.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        if row["genres"]:
            # split genres correctly
            genres = [g.strip() for g in row["genres"].split(",") if g.strip()]

            # convert HOURS to float safely
            try:
                hours_value = float(row["hours"])
            except:
                hours_value = 0.0

            # add hours to EVERY genre
            for genre in genres:
                hours_by_genre[genre] = hours_by_genre.get(genre, 0.0) + hours_value



    clean_hours = [(g, h) for g, h in hours_by_genre.items()]
    sorted_hours = sorted(clean_hours, key=lambda x: x[1], reverse=True)

    top_10_hours = sorted_hours[:10]
    if len(sorted_hours) > 10:
        others_hours = sum(h for (_, h) in sorted_hours[10:])
        top_10_hours.append(("Others", others_hours))

    hours_genre_labels = [g for g, _ in top_10_hours]
    hours_genre_data = [h for _, h in top_10_hours]

    return render_template(
        "stats.html",
        total_hours=total_hours,
        avg_rating=avg_rating,
        rated_count=len(ratings),
        top_rows=top_rows,
        genre_labels=genre_labels,
        genre_data=genre_data,
        hours_genre_labels=hours_genre_labels,
        hours_genre_data=hours_genre_data
    )

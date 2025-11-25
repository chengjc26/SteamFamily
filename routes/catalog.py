from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user, login_required
from models.db import get_db

EXCLUDED_TAGS = {
    "Singleplayer", "Multiplayer", "Free to Play"
}

catalog_bp = Blueprint("catalog", __name__, url_prefix="/")

# ============================================================
#                     GAME LIST
# ============================================================
@catalog_bp.route("/games")
@login_required
def games():
    db = get_db()

    sort = request.args.get("sort", "alpha")

    rows = db.execute("""
        SELECT 
            g.appid,
            g.title,
            COALESCE(g.custom_cover_url, g.cover_url) AS cover_url,
            COALESCE(ph.hours, 0) AS hours,
            ug.rating AS user_rating
        FROM owned_games og
        JOIN games g ON og.appid = g.appid
        LEFT JOIN player_hours ph 
            ON ph.appid = g.appid AND ph.steamid = og.steamid
        LEFT JOIN user_game_list ug
            ON ug.appid = g.appid AND ug.user_id = ?
        WHERE og.steamid = ?
    """, (current_user.id, current_user.steamid)).fetchall()

    # -------- APPLY SORTING --------
    if sort == "hours":
        rows = sorted(rows, key=lambda r: (r["hours"] or 0), reverse=True)
    elif sort == "rating":
        rows = sorted(rows, key=lambda r: (r["user_rating"] or -1), reverse=True)
    else:
        rows = sorted(rows, key=lambda r: r["title"].lower())

    return render_template("games.html", games=rows, sort=sort)



# ============================================================
#                     GAME DETAIL PAGE (WITH TAGS)
# ============================================================
@catalog_bp.route("/game/<int:appid>")
@login_required
def game_detail(appid):
    db = get_db()

    game = db.execute("""
        SELECT
            appid, title, description, genres, tags, release_year,
            COALESCE(custom_cover_url, cover_url) AS cover_url
        FROM games
        WHERE appid=?
    """, (appid,)).fetchone()

    hours_row = db.execute("""
        SELECT hours
        FROM player_hours
        WHERE steamid=? AND appid=?
    """, (current_user.steamid, appid)).fetchone()

    final_hours = hours_row["hours"] if hours_row else 0

    user_game = db.execute("""
        SELECT rating, notes, play_order
        FROM user_game_list
        WHERE user_id=? AND appid=?
    """, (current_user.id, appid)).fetchone()

    family = db.execute("""
        SELECT u.display_name, ug.rating, ug.notes
        FROM user_game_list ug
        JOIN users u ON u.id = ug.user_id
        WHERE ug.appid = ?
    """, (appid,)).fetchall()

    # Convert tag string → list
    tag_list = game["tags"].split(",") if game["tags"] else []

    return render_template(
        "game_detail.html",
        game=game,
        tags=tag_list,
        hours=final_hours,
        user_rating=user_game["rating"] if user_game else None,
        user_notes=user_game["notes"] if user_game else "",
        user_game=user_game,
        family=family
    )


# ============================================================
#                     SAVE ALL (unchanged)
# ============================================================
@catalog_bp.route("/game/<int:appid>/save_all", methods=["POST"])
@login_required
def save_all(appid):
    db = get_db()

    hours_text = request.form.get("hours", "").strip()
    rating_text = request.form.get("rating", "").strip()
    notes = request.form.get("notes", "")

    try:
        hours_value = float(hours_text)
    except:
        hours_value = 0.0

    try:
        rating_value = int(rating_text)
        rating_value = max(1, min(10, rating_value))
    except:
        rating_value = None

    steamid = current_user.steamid
    user_id = current_user.id

    cur = db.execute("""
        UPDATE player_hours SET hours = ?
        WHERE steamid = ? AND appid = ?
    """, (hours_value, steamid, appid))

    if cur.rowcount == 0:
        db.execute("""
            INSERT INTO player_hours (steamid, appid, hours)
            VALUES (?, ?, ?)
        """, (steamid, appid, hours_value))

    cur = db.execute("""
        UPDATE user_game_list SET rating = ?, notes = ?
        WHERE user_id = ? AND appid = ?
    """, (rating_value, notes, user_id, appid))

    if cur.rowcount == 0:
        db.execute("""
            INSERT INTO user_game_list (user_id, appid, rating, notes)
            VALUES (?, ?, ?, ?)
        """, (user_id, appid, rating_value, notes))

    db.commit()
    return redirect(url_for("catalog.game_detail", appid=appid))


# ============================================================
#                     UPDATE HOURS (unchanged)
# ============================================================
@catalog_bp.route("/game/<int:appid>/update_hours", methods=["POST"])
@login_required
def update_hours(appid):
    db = get_db()

    hours_text = request.form.get("hours", "").strip()
    try:
        hours_value = float(hours_text)
    except:
        hours_value = 0.0

    db.execute("""
        UPDATE player_hours
        SET hours = ?
        WHERE steamid = ? AND appid = ?
    """, (hours_value, current_user.steamid, appid))

    if db.total_changes == 0:
        db.execute("""
            INSERT INTO player_hours (steamid, appid, hours)
            VALUES (?, ?, ?)
        """, (current_user.steamid, appid, hours_value))

    db.commit()
    return redirect(url_for("catalog.game_detail", appid=appid))


# ============================================================
#                     COVER CUSTOMIZATION (unchanged)
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
#                     FAMILY PAGE (unchanged)
# ============================================================
import statistics

@catalog_bp.route("/family")
@login_required
def family():
    db = get_db()

    sort = request.args.get("sort", "alpha")

    games_raw = db.execute("""
        SELECT 
            g.appid,
            g.title,
            COALESCE(g.custom_cover_url, g.cover_url) AS cover_url
        FROM games g
        JOIN owned_games og ON g.appid = og.appid
        GROUP BY g.appid
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
                ug.rating
            FROM users u
            LEFT JOIN player_hours ph ON ph.steamid = u.steamid AND ph.appid = ?
            LEFT JOIN user_game_list ug ON ug.user_id = u.id AND ug.appid = ?
        """, (appid, appid)).fetchall()
        clean_members = []
        for m in member_rows:
            clean_members.append({
                "user_id": m["user_id"],
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "hours": float(m["hours"] or 0),   # <-- FIXED
                "rating": m["rating"],
            })

        # Ratings list
        ratings = [m["rating"] for m in member_rows if m["rating"] is not None]

        # Average rating
        avg_rating = sum(ratings)/len(ratings) if ratings else None

        # ⭐ TOTAL hours across entire family (new)
        total_hours = sum(m["hours"] for m in member_rows)

        # Standard deviation (tie-breaker)
        if len(ratings) >= 2:
            stdev_rating = statistics.pstdev(ratings)
        else:
            stdev_rating = 9999  # worse tie-break score

        games.append({
            "appid": appid,
            "title": row["title"],
            "cover_url": row["cover_url"],
            "members": clean_members,
            "avg_rating": avg_rating,
            "total_hours": sum(m["hours"] for m in clean_members),
            "std_rating": stdev_rating,
        })

    # -------- SORTING --------

    if sort == "rating":
        games = sorted(
            games,
            key=lambda g: (
                g["avg_rating"] if g["avg_rating"] is not None else -1,
                -g["std_rating"]  # lower better
            ),
            reverse=True
        )

    elif sort == "hours":
        games = sorted(games, key=lambda g: g["total_hours"], reverse=True)

    else:
        games = sorted(games, key=lambda g: g["title"].lower())

    return render_template("family.html", games=games, sort=sort)
# ============================================================
#                     FAMILY STATS PAGE (NEW)
# ============================================================
@catalog_bp.route("/family_stats")
@login_required
def family_stats():
    db = get_db()

    # ============================================
    # 1. Load family users (convert Row → dict)
    # ============================================
    raw_users = db.execute("""
        SELECT id, display_name
        FROM users
        ORDER BY display_name COLLATE NOCASE
    """).fetchall()

    users = [
        {
            "id": u["id"],
            "display_name": u["display_name"]
        }
        for u in raw_users
    ]

    # ============================================
    # 2. Load ratings for all users
    # ============================================
    raw_ratings = db.execute("""
        SELECT user_id, appid, rating
        FROM user_game_list
        WHERE rating IS NOT NULL
    """).fetchall()

    # Convert Rows → dicts to avoid JSON error
    ratings = [
        {
            "user_id": r["user_id"],
            "appid": r["appid"],
            "rating": r["rating"]
        }
        for r in raw_ratings
    ]

    # ============================================
    # 3. Load game tags
    # ============================================
    raw_tag_map = db.execute("""
        SELECT appid, tags
        FROM games
    """).fetchall()

    tag_map = {}
    for row in raw_tag_map:
        if row["tags"]:
            tag_map[row["appid"]] = [
                t.strip() for t in row["tags"].split(",") if t.strip()
            ]

    # ============================================
    # 4. Compute similarity between users
    # ============================================
    from collections import defaultdict
    user_ratings = defaultdict(dict)

    for r in ratings:
        user_ratings[r["user_id"]][r["appid"]] = r["rating"]

    similarity = {u["id"]: {} for u in users}

    for u1 in users:
        for u2 in users:
            if u1["id"] == u2["id"]:
                similarity[u1["id"]][u2["id"]] = 1.0
                continue

            overlap = set(user_ratings[u1["id"]]).intersection(
                user_ratings[u2["id"]]
            )

            if not overlap:
                similarity[u1["id"]][u2["id"]] = 0
            else:
                diffs = []
                for app in overlap:
                    diffs.append(
                        abs(
                            user_ratings[u1["id"]][app]
                            - user_ratings[u2["id"]][app]
                        )
                    )

                similarity[u1["id"]][u2["id"]] = max(
                    0, 1 - (sum(diffs) / len(diffs) / 10)
                )  # scaled to 1–0

    # Convert similarity → JSON-safe dicts
    similarity_out = {
        str(uid): {str(k): float(v) for k, v in similarity[uid].items()}
        for uid in similarity
    }

    # ============================================
    # 5. Genre averages per user
    # ============================================
    genre_totals = defaultdict(lambda: defaultdict(list))

    for r in ratings:
        appid = r["appid"]
        if appid not in tag_map:
            continue

        for tag in tag_map[appid]:
            if tag in EXCLUDED_TAGS:
                continue
            genre_totals[r["user_id"]][tag].append(r["rating"])

    genre_avgs = {}
    for user_id, tag_values in genre_totals.items():
        genre_avgs[user_id] = {
            tag: sum(vals) / len(vals)
            for tag, vals in tag_values.items()
        }

    # Convert genre → JSON-safe dicts
    genre_out = {
        str(uid): {tag: float(avg) for tag, avg in genre_avgs.get(uid, {}).items()}
        for uid in {u["id"] for u in users}
    }

    # ============================================
    # 6. Most played game per user
    # ============================================
    raw_hours = db.execute("""
        SELECT ph.steamid, g.title, ph.hours
        FROM player_hours ph
        JOIN games g ON g.appid = ph.appid
    """).fetchall()

    hours_map = defaultdict(list)
    for row in raw_hours:
        hours_map[row["steamid"]].append({
            "title": row["title"],
            "hours": float(row["hours"] or 0)
        })

    most_played = {}
    for user in raw_users:
        uid = user["id"]
        steamid = db.execute("SELECT steamid FROM users WHERE id=?", (uid,)).fetchone()["steamid"]

        entries = hours_map.get(steamid, [])
        if entries:
            entries.sort(key=lambda x: x["hours"], reverse=True)
            most_played[uid] = entries[0]["title"]
        else:
            most_played[uid] = "None"

    # ============================================
    # SEND TO TEMPLATE
    # ============================================
    return render_template(
        "family_stats.html",
        users=users,
        similarity=similarity_out,
        genre_avgs=genre_out,
        most_played=most_played
    )



# ============================================================
#                     STATS PAGE (NOW USES TAGS)
# ============================================================
@catalog_bp.route("/stats")
@login_required
def stats():
    db = get_db()
    steamid = current_user.steamid

    # -------------------------------
    # TOTAL HOURS
    # -------------------------------
    total_hours_row = db.execute("""
        SELECT IFNULL(SUM(hours), 0) AS total
        FROM player_hours
        WHERE steamid=?
    """, (steamid,)).fetchone()
    total_hours = float(total_hours_row["total"])

    # -------------------------------
    # AVERAGE RATING
    # -------------------------------
    rating_rows = db.execute("""
        SELECT rating FROM user_game_list 
        WHERE user_id = ? AND rating IS NOT NULL
    """, (current_user.id,)).fetchall()

    ratings = [r["rating"] for r in rating_rows]
    avg_rating = sum(ratings)/len(ratings) if ratings else None

    # ===============================
    # TAG COUNTS (TOP 10)
    # ===============================
    tag_count = {}
    rows = db.execute("""
        SELECT g.tags
        FROM games g
        JOIN owned_games og ON og.appid = g.appid
        WHERE og.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        if row["tags"]:
            for tag in [t.strip() for t in row["tags"].split(",") if t.strip()]:
                if tag not in EXCLUDED_TAGS:
                    tag_count[tag] = tag_count.get(tag, 0) + 1

    sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
    top_tags = sorted_tags[:10]  # <-- TOP 10

    tag_labels = [g for g, _ in top_tags]
    tag_data = [c for _, c in top_tags]


    # ===============================
    # HOURS BY TAG (TOP 10)
    # ===============================
    hours_by_tag = {}
    rows = db.execute("""
        SELECT g.tags, ph.hours
        FROM games g
        JOIN player_hours ph ON g.appid = ph.appid
        WHERE ph.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        if row["tags"]:
            tags = [t.strip() for t in row["tags"].split(",") if t.strip()]
            hours_value = float(row["hours"] or 0)

            for tag in tags:
                if tag not in EXCLUDED_TAGS:
                    hours_by_tag[tag] = hours_by_tag.get(tag, 0.0) + hours_value

    sorted_hours = sorted(hours_by_tag.items(), key=lambda x: x[1], reverse=True)
    top_hours = sorted_hours[:10]  # <-- TOP 10

    hours_tag_labels = [g for g, _ in top_hours]
    hours_tag_data = [h for _, h in top_hours]

    # ===============================
    # GAMES PER RELEASE YEAR
    # ===============================
    year_counts = {}
    rows = db.execute("""
        SELECT release_year
        FROM games g
        JOIN owned_games og ON og.appid = g.appid
        WHERE og.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        year = row["release_year"]
        if year and str(year).isdigit():
            year = int(year)
            year_counts[year] = year_counts.get(year, 0) + 1

    year_labels = sorted(year_counts.keys())
    year_data = [year_counts[y] for y in year_labels]

    # ===============================
    # GAMES BY RATING (1–10)
    # ===============================
    rating_count = {}
    rows = db.execute("""
        SELECT rating
        FROM user_game_list
        WHERE user_id = ? AND rating IS NOT NULL
    """, (current_user.id,)).fetchall()

    for row in rows:
        r = int(row["rating"])
        rating_count[r] = rating_count.get(r, 0) + 1

    rating_labels = sorted(rating_count.keys())
    rating_data = [rating_count[r] for r in rating_labels]

    # -------------------------------
    # CLEAN LABELS
    # -------------------------------
    def clean_list(lst):
        return [str(x).strip() for x in lst if x and str(x).strip()]

    return render_template(
        "stats.html",
        total_hours=total_hours,
        avg_rating=avg_rating,
        rated_count=len(ratings),

        # tags (TOP 20)
        tag_labels=clean_list(tag_labels),
        tag_data=tag_data,

        # hours by tag (TOP 20)
        hours_tag_labels=clean_list(hours_tag_labels),
        hours_tag_data=hours_tag_data,

        # year
        year_labels=year_labels,
        year_counts=year_data,

        # rating distribution
        rating_labels=rating_labels,
        rating_counts=rating_data
    )
@catalog_bp.route("/user/<int:user_id>/stats")
@login_required
def user_stats(user_id):
    db = get_db()

    # load the selected user
    user = db.execute("""
        SELECT id, steamid, display_name
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not user:
        return "User not found", 404

    steamid = user["steamid"]

    # TOTAL HOURS
    total_hours_row = db.execute("""
        SELECT IFNULL(SUM(hours), 0) AS total
        FROM player_hours
        WHERE steamid=?
    """, (steamid,)).fetchone()
    total_hours = float(total_hours_row["total"])

    # AVERAGE RATING
    rating_rows = db.execute("""
        SELECT rating FROM user_game_list 
        WHERE user_id = ? AND rating IS NOT NULL
    """, (user_id,)).fetchall()

    ratings = [r["rating"] for r in rating_rows]
    avg_rating = sum(ratings)/len(ratings) if ratings else None

    # TAG COUNTS
    tag_count = {}
    rows = db.execute("""
        SELECT g.tags
        FROM games g
        JOIN owned_games og ON og.appid = g.appid
        WHERE og.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        if row["tags"]:
            for tag in [t.strip() for t in row["tags"].split(",") if t.strip()]:
                if tag not in EXCLUDED_TAGS:
                    tag_count[tag] = tag_count.get(tag, 0) + 1

    sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
    top_tags = sorted_tags[:10]

    tag_labels = [g for g, _ in top_tags]
    tag_data = [c for _, c in top_tags]

    # HOURS BY TAG
    hours_by_tag = {}
    rows = db.execute("""
        SELECT g.tags, ph.hours
        FROM games g
        JOIN player_hours ph ON g.appid = ph.appid
        WHERE ph.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        if row["tags"]:
            tags = [t.strip() for t in row["tags"].split(",") if t.strip()]
            hours_value = float(row["hours"] or 0)
            for tag in tags:
                if tag not in EXCLUDED_TAGS:
                    hours_by_tag[tag] = hours_by_tag.get(tag, 0.0) + hours_value

    sorted_hours = sorted(hours_by_tag.items(), key=lambda x: x[1], reverse=True)
    top_hours = sorted_hours[:10]

    hours_tag_labels = [g for g, _ in top_hours]
    hours_tag_data = [h for _, h in top_hours]

    # ===============================
    # GAMES PER RELEASE YEAR (FIXED!)
    # ===============================
    year_counts = {}
    rows = db.execute("""
        SELECT release_year
        FROM games g
        JOIN owned_games og ON og.appid = g.appid
        WHERE og.steamid = ?
    """, (steamid,)).fetchall()

    for row in rows:
        year = row["release_year"]
        if year and str(year).isdigit():
            year = int(year)
            year_counts[year] = year_counts.get(year, 0) + 1

    year_labels = sorted(year_counts.keys())
    year_data = [year_counts[y] for y in year_labels]

    # RATING DISTRIBUTION
    rating_count = {}
    rows = db.execute("""
        SELECT rating
        FROM user_game_list
        WHERE user_id = ? AND rating IS NOT NULL
    """, (user_id,)).fetchall()

    for row in rows:
        r = int(row["rating"])
        rating_count[r] = rating_count.get(r, 0) + 1

    rating_labels = sorted(rating_count.keys())
    rating_data = [rating_count[r] for r in rating_labels]

    return render_template(
        "stats.html",
        total_hours=total_hours,
        avg_rating=avg_rating,
        rated_count=len(ratings),

        tag_labels=tag_labels,
        tag_data=tag_data,

        hours_tag_labels=hours_tag_labels,
        hours_tag_data=hours_tag_data,

        # ⭐ FIXED — now populated
        year_labels=year_labels,
        year_counts=year_data,

        rating_labels=rating_labels,
        rating_counts=rating_data,

        viewing_user_name=user["display_name"]
    )

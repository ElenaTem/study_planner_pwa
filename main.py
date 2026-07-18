import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database_manager import db, User, StudySession, utc_now, DailyStudyGoal
from datetime import datetime, timezone, timedelta


app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FOLDER = os.path.join(BASE_DIR, ".database")
DATABASE_PATH = os.path.join(DB_FOLDER, "study_planner.db")

# Checks if the database folder exists and makes a new one if it doesnt 
os.makedirs(DB_FOLDER, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key"

db.init_app(app)

with app.app_context():
    db.create_all()

print("Using database file:", DATABASE_PATH)




# -------------------
# LOGIN PAGE
# -------------------


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_identifier = request.form.get("login_identifier", "").strip()

        password = request.form.get("password", "")

        if not login_identifier or not password:
            return render_template("login.html", error="Please fill in all fields.")

        # Find the account using either username or email
        user = User.query.filter(
            (User.username == login_identifier) | (db.func.lower(User.user_email) == login_identifier.lower())).first()

        # Check that the account exists
        if user is None:
            return render_template("login.html", error="Incorrect username, email, or password.")

        # Check that the entered password matches the stored hash
        if not check_password_hash(user.password_hash, password):
            return render_template("login.html", error="Incorrect username, email, or password.")

        # Login was successful
        session.clear()
        session["user_id"] = user.user_id
        session["username"] = user.username

        return redirect(url_for("home"))

    return render_template("login.html")


# -------------------
# SIGN UP
# -------------------


@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if request.method == "POST":
        username = request.form.get("username", "").strip()

        user_email = request.form.get("user_email","").strip().lower()

        password = request.form.get("password", "")

        if not username or not user_email or not password:
            return render_template("sign_up.html", error="Please fill in all fields.")

        if len(password) < 8:
            return render_template("sign_up.html", error="Password must be at least 8 characters long.")

        existing_user = User.query.filter((User.username == username) | (db.func.lower(User.user_email) == user_email)).first()

        if existing_user:
            return render_template("sign_up.html", error="Username or email already exists.")

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        new_user = User(username=username, user_email=user_email, password_hash=password_hash)

        #saves the new accounts to the database
        db.session.add(new_user)
        db.session.commit()

        # Automatically log in the newly created user
        session.clear()
        session["user_id"] = new_user.user_id
        session["username"] = new_user.username

        # Takes the new user to the home page
        return redirect(url_for("home"))

    return render_template("sign_up.html")


# -------------------
# MAIN PAGES
# ------------------- 

@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("home.html", username=session.get("username"))



@app.route("/timer")
def timer():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("timer.html")


@app.route("/study-session")
def study_session():
    if "user_id" not in session:
        return redirect(url_for("login"))

    tree_urls = [
        url_for(
            "static",
            filename=f"images/tree_{stage}.png"
        )
        for stage in range(1, 8)
    ]

    return render_template(
        "study_session.html",
        tree_urls=tree_urls
    )

@app.route(
    "/api/study-sessions/start",
    methods=["POST"]
)
def start_study_session():
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    request_data = request.get_json(silent=True) or {}

    try:
        duration_minutes = int(
            request_data.get("duration_minutes")
        )
    except (TypeError, ValueError):
        return jsonify({
            "error": "The study duration is invalid."
        }), 400

    if duration_minutes < 15:
        return jsonify({
            "error": (
                "A study session must be at least "
                "15 minutes."
            )
        }), 400

    if duration_minutes > 720:
        return jsonify({
            "error": (
                "A study session cannot be longer "
                "than 12 hours."
            )
        }), 400

    if duration_minutes % 15 != 0:
        return jsonify({
            "error": (
                "The study duration must use "
                "15-minute intervals."
            )
        }), 400

    current_time = utc_now()

    old_active_sessions = StudySession.query.filter_by(
        user_id=session["user_id"],
        status="active"
    ).all()

    for old_session in old_active_sessions:
        elapsed_seconds = int(
            (
                current_time -
                old_session.started_at
            ).total_seconds()
        )

        old_session.actual_duration_seconds = max(
            0,
            min(
                elapsed_seconds,
                old_session.planned_duration_seconds
            )
        )

        old_session.ended_at = current_time
        old_session.status = "replaced"

    planned_duration_seconds = duration_minutes * 60

    new_study_session = StudySession(
        user_id=session["user_id"],
        planned_duration_seconds=(
            planned_duration_seconds
        ),
        actual_duration_seconds=0,
        started_at=current_time,
        status="active"
    )

    db.session.add(new_study_session)
    db.session.commit()

    start_time_milliseconds = int(time.time() * 1000)

    end_time_milliseconds = (
        start_time_milliseconds +
        planned_duration_seconds * 1000
    )

    return jsonify({
        "study_session_id": (
            new_study_session.study_session_id
        ),
        "planned_duration_seconds": (
            planned_duration_seconds
        ),
        "start_time_ms": start_time_milliseconds,
        "end_time_ms": end_time_milliseconds
    }), 201


@app.route(
    "/api/study-sessions/<int:study_session_id>/finish",
    methods=["POST"]
)
def finish_study_session(study_session_id):
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    study_session_record = db.session.get(
        StudySession,
        study_session_id
    )

    if study_session_record is None:
        return jsonify({
            "error": "Study session not found."
        }), 404

    if (
        study_session_record.user_id
        != session["user_id"]
    ):
        return jsonify({
            "error": "You cannot modify this session."
        }), 403


    if study_session_record.status != "active":
        return jsonify({
            "study_session_id": (
                study_session_record.study_session_id
            ),
            "actual_duration_seconds": (
                study_session_record
                .actual_duration_seconds
            ),
            "status": study_session_record.status
        }), 200

    request_data = request.get_json(silent=True) or {}

    requested_status = request_data.get(
        "status",
        "ended_early"
    )

    allowed_statuses = {
        "completed",
        "ended_early",
        "cancelled_navigation"
    }

    if requested_status not in allowed_statuses:
        return jsonify({
            "error": "Invalid study-session status."
        }), 400

    current_time = utc_now()

    elapsed_seconds = int(
        (
            current_time -
            study_session_record.started_at
        ).total_seconds()
    )

    elapsed_seconds = max(0, elapsed_seconds)

    if requested_status == "completed":
        if (
            elapsed_seconds + 2
            < study_session_record
                .planned_duration_seconds
        ):
            return jsonify({
                "error": (
                    "The study session has not "
                    "finished yet."
                )
            }), 400

        actual_duration_seconds = (
            study_session_record
                .planned_duration_seconds
        )

    else:
        actual_duration_seconds = min(
            elapsed_seconds,
            study_session_record
                .planned_duration_seconds
        )

    study_session_record.actual_duration_seconds = (
        actual_duration_seconds
    )

    study_session_record.ended_at = current_time
    study_session_record.status = requested_status

    db.session.commit()

    return jsonify({
        "study_session_id": (
            study_session_record.study_session_id
        ),
        "actual_duration_seconds": (
            actual_duration_seconds
        ),
        "status": requested_status
    }), 200


@app.route("/api/study-sessions/daily-total")
def daily_study_total():
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    try:
        day_start_ms = int(
            request.args.get("day_start_ms")
        )

        day_end_ms = int(
            request.args.get("day_end_ms")
        )

    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid date range."
        }), 400

    if day_end_ms <= day_start_ms:
        return jsonify({
            "error": "Invalid date range."
        }), 400

    # Convert the user's local-day boundaries into UTC.
    day_start_utc = datetime.fromtimestamp(
        day_start_ms / 1000,
        tz=timezone.utc
    ).replace(tzinfo=None)

    day_end_utc = datetime.fromtimestamp(
        day_end_ms / 1000,
        tz=timezone.utc
    ).replace(tzinfo=None)

    study_session_records = StudySession.query.filter(
        StudySession.user_id == session["user_id"],

        # Only saved/finished sessions are included here.
        StudySession.ended_at.isnot(None),

        # Find sessions that overlap the selected day.
        StudySession.started_at < day_end_utc,
        StudySession.ended_at > day_start_utc
    ).all()

    total_seconds = 0

    for study_session_record in study_session_records:
        overlap_start = max(
            study_session_record.started_at,
            day_start_utc
        )

        overlap_end = min(
            study_session_record.ended_at,
            day_end_utc
        )

        if overlap_end > overlap_start:
            total_seconds += int(
                (
                    overlap_end -
                    overlap_start
                ).total_seconds()
            )

    return jsonify({
        "total_seconds": total_seconds
    }), 200



@app.route(
    "/api/daily-study-goal",
    methods=["GET", "POST"]
)
def daily_study_goal():
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    if request.method == "GET":
        date_text = request.args.get("date")

        try:
            goal_date = datetime.strptime(
                date_text,
                "%Y-%m-%d"
            ).date()

        except (TypeError, ValueError):
            return jsonify({
                "error": "Invalid goal date."
            }), 400

        goal_record = DailyStudyGoal.query.filter_by(
            user_id=session["user_id"],
            goal_date=goal_date
        ).first()

        if goal_record is None:
            return jsonify({
                "exists": False,
                "goal_minutes": None
            }), 200

        return jsonify({
            "exists": True,
            "goal_minutes": goal_record.goal_minutes
        }), 200

    request_data = request.get_json(silent=True) or {}

    date_text = request_data.get("date")

    try:
        goal_date = datetime.strptime(
            date_text,
            "%Y-%m-%d"
        ).date()

        goal_minutes = int(
            request_data.get("goal_minutes")
        )

    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid daily goal."
        }), 400

    if goal_minutes < 15:
        return jsonify({
            "error": (
                "The daily goal must be at least "
                "15 minutes."
            )
        }), 400

    if goal_minutes > 720:
        return jsonify({
            "error": (
                "The daily goal cannot exceed "
                "12 hours."
            )
        }), 400

    if goal_minutes % 15 != 0:
        return jsonify({
            "error": (
                "The daily goal must use "
                "15-minute intervals."
            )
        }), 400

    goal_record = DailyStudyGoal.query.filter_by(
        user_id=session["user_id"],
        goal_date=goal_date
    ).first()

    if goal_record is None:
        goal_record = DailyStudyGoal(
            user_id=session["user_id"],
            goal_date=goal_date,
            goal_minutes=goal_minutes
        )

        db.session.add(goal_record)

    else:
        goal_record.goal_minutes = goal_minutes

    db.session.commit()

    return jsonify({
        "exists": True,
        "goal_minutes": goal_record.goal_minutes
    }), 200

@app.route("/api/study-analytics/month", methods=["POST"])
def monthly_study_analytics():
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    request_data = request.get_json(silent=True) or {}

    day_boundaries_ms = request_data.get(
        "day_boundaries_ms"
    )

    if not isinstance(day_boundaries_ms, list):
        return jsonify({
            "error": "Invalid day boundaries."
        }), 400

    if not 29 <= len(day_boundaries_ms) <= 32:
        return jsonify({
            "error": "Invalid number of days."
        }), 400

    try:
        day_boundaries_ms = [
            int(boundary)
            for boundary in day_boundaries_ms
        ]

    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid day boundaries."
        }), 400

    for index in range(len(day_boundaries_ms) - 1):
        if (
            day_boundaries_ms[index]
            >= day_boundaries_ms[index + 1]
        ):
            return jsonify({
                "error": (
                    "Day boundaries must be "
                    "in chronological order."
                )
            }), 400

    utc_boundaries = [
        datetime.fromtimestamp(
            boundary / 1000,
            tz=timezone.utc
        ).replace(tzinfo=None)
        for boundary in day_boundaries_ms
    ]

    month_start = utc_boundaries[0]
    month_end = utc_boundaries[-1]

    study_session_records = StudySession.query.filter(
        StudySession.user_id == session["user_id"],
        StudySession.actual_duration_seconds > 0,
        StudySession.started_at < month_end
    ).all()

    daily_seconds = [
        0 for _ in range(len(utc_boundaries) - 1)
    ]

    for study_record in study_session_records:
        session_start = study_record.started_at

        session_end = (
            study_record.started_at
            + timedelta(
                seconds=study_record.actual_duration_seconds
            )
        )

        if session_end <= month_start:
            continue

        for day_index in range(
            len(utc_boundaries) - 1
        ):
            day_start = utc_boundaries[day_index]
            day_end = utc_boundaries[day_index + 1]

            overlap_start = max(
                session_start,
                day_start
            )

            overlap_end = min(
                session_end,
                day_end
            )

            if overlap_end > overlap_start:
                daily_seconds[day_index] += int(
                    (
                        overlap_end
                        - overlap_start
                    ).total_seconds()
                )

    return jsonify({
        "daily_seconds": daily_seconds
    }), 200









@app.route("/calendar")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("calendar.html")



@app.route("/users")
def users():
    all_users = User.query.all()

    if not all_users:
        return "No users found."

    return "<br>".join(
        [f"{user.user_id} - {user.username} - {user.user_email}" for user in all_users]
    )


if __name__ == "__main__":
    app.run(debug=True)


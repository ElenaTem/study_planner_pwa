import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database_manager import (
    db,
    User,
    Subject,
    StudySession,
    utc_now,
    DailyStudyGoal,
    NotepadItem
)
from datetime import datetime, timezone, timedelta
from sqlalchemy import inspect, text


# main.py creates and configures the Flask application; 
# defines page routes; 
# receives API requests from JavaScript;

# ---------------------------------------------------------------------------
# APPLICATION AND DATABASE CONFIGURATION
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Build an absolute database path from this file's location. This keeps the
# SQLite database in the project's hidden .database folder regardless of the
# directory from which the Flask application is started.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FOLDER = os.path.join(BASE_DIR, ".database")
DATABASE_PATH = os.path.join(DB_FOLDER, "study_planner.db")

# Create the database folder on the application's first run.
os.makedirs(DB_FOLDER, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key"

db.init_app(app)

def run_database_migrations():
    """
    db.create_all() cannot add to an existing database.

    Existing study sessions receive a NULL subject_id, which
    is displayed as the built-in Focus category. Existing
    users who already have subjects are marked as having
    completed the subject-selection onboarding.
    """
    # SQLAlchemy's inspector allows the application to check an existing
    # database before attempting any ALTER TABLE statements.
    database_inspector = inspect(db.engine)
    table_names = database_inspector.get_table_names()

    if "users" in table_names:
        user_columns = {
            column["name"]
            for column in database_inspector.get_columns(
                "users"
            )
        }

        # Older databases do not contain this onboarding flag, so it is added
        # without deleting or recreating the users table.
        if "subject_setup_completed" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE users "
                    "ADD COLUMN subject_setup_completed "
                    "BOOLEAN NOT NULL DEFAULT 0"
                ))

        # Users who already created subjects before this field existed should
        # not be sent through subject onboarding again.
        if "subjects" in table_names:
            with db.engine.begin() as connection:
                connection.execute(text(
                    "UPDATE users "
                    "SET subject_setup_completed = 1 "
                    "WHERE subject_setup_completed = 0 "
                    "AND user_id IN ("
                    "SELECT DISTINCT user_id FROM subjects"
                    ")"
                ))

    # A brand-new database may not yet contain this table at migration time.
    if "study_sessions" not in table_names:
        return

    study_session_columns = {
        column["name"]
        for column in database_inspector.get_columns(
            "study_sessions"
        )
    }

    # A nullable foreign key preserves old study sessions: NULL sessions are
    # displayed under the built-in "Focus" analytics category.
    if "subject_id" not in study_session_columns:
        with db.engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE study_sessions "
                "ADD COLUMN subject_id INTEGER "
                "REFERENCES subjects(subject_id)"
            ))

    # Indexing the foreign key makes subject-based lookups more efficient.
    with db.engine.begin() as connection:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS "
            "ix_study_sessions_subject_id "
            "ON study_sessions(subject_id)"
        ))

with app.app_context():
    # create_all handles new tables; the migration function handles new
    # columns required by databases created by an older project version.
    db.create_all()
    run_database_migrations()

print("Using database file:", DATABASE_PATH)

RESERVED_SUBJECT_NAMES = {
    "focus",
    "other"
}

# ---------------------------------------------------------------------------
# SUBJECT HELPERS
# ---------------------------------------------------------------------------

def clean_subject_name(subject_name):
    """Return a display name with extra whitespace removed."""
    if not isinstance(subject_name, str):
        return ""

    return " ".join(subject_name.split())

def normalise_subject_name(subject_name):
    """Return a case-insensitive value used for duplicate checks."""
    return clean_subject_name(subject_name).casefold()

def subject_to_dictionary(subject):
    # Convert a database model into the JSON-ready structure expected by the
    # subject-management JavaScript.
    return {
        "subject_id": subject.subject_id,
        "subject_name": subject.subject_name,
        "is_active": subject.is_active
    }

def user_has_active_subjects(user_id):
    # Only one matching row is needed to enforce the "at least one subject"
    # onboarding requirement, so first() avoids loading every subject.
    return Subject.query.filter_by(
        user_id=user_id,
        is_active=True
    ).first() is not None

def user_completed_subject_setup(user_id):
    # db.session.get performs a primary-key lookup for the current account.
    current_user = db.session.get(User, user_id)

    return bool(
        current_user
        and current_user.subject_setup_completed
    )

def subject_setup_redirect():
    """Redirect users who have not completed first-time setup."""
    if not user_completed_subject_setup(session["user_id"]):
        return redirect(url_for(
            "manage_subjects",
            onboarding=1
        ))

    return None

# ---------------------------------------------------------------------------
# AUTHENTICATION AND ACCOUNT MANAGEMENT
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    # The root address uses the login page as the application's entry point.
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    # GET displays the form; POST validates the submitted credentials.
    if request.method == "POST":
        login_identifier = request.form.get("login_identifier", "").strip()

        password = request.form.get("password", "")

        if not login_identifier or not password:
            return render_template("login.html", error="Please fill in all fields.")

        # Allow the same field to accept a username or a case-insensitive email.
        user = User.query.filter(
            (User.username == login_identifier) | (db.func.lower(User.user_email) == login_identifier.lower())).first()

        # Check that the account exists
        if user is None:
            return render_template("login.html", error="Incorrect username, email, or password.")

        # Check that the entered password matches the stored hash
        if not check_password_hash(user.password_hash, password):
            return render_template("login.html", error="Incorrect username, email, or password.")

        # Replace any previous session data with the authenticated user's ID
        # and display name. Routes use this ID to protect user-owned records.
        session.clear()
        session["user_id"] = user.user_id
        session["username"] = user.username

        if user.subject_setup_completed:
            return redirect(url_for("home"))

        return redirect(url_for(
            "manage_subjects",
            onboarding=1
        ))

    return render_template("login.html")

@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    # Validate all input before creating the database record.
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

        # Store a one-way password hash rather than the original password.
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        new_user = User(username=username, user_email=user_email, password_hash=password_hash)

        # Save the account before placing its generated user_id in the session.
        db.session.add(new_user)
        db.session.commit()

        # Automatically log in the newly created user
        session.clear()
        session["user_id"] = new_user.user_id
        session["username"] = new_user.username

        # New users must choose at least one subject
        # before entering the dashboard.
        return redirect(url_for(
            "manage_subjects",
            onboarding=1
        ))

    return render_template("sign_up.html")

@app.route("/account")
def account():
    """Keep old Account links working by opening Subject Settings."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("manage_subjects"))

@app.route("/logout", methods=["GET", "POST"])
def logout():
    # Clearing the server-side session removes the user's authenticated state.
    session.clear()
    return redirect(url_for("login"))

@app.route("/api/account/verify-password", methods=["POST"])
def verify_account_password():
    # This separate check is used before sensitive account actions in the UI.
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    request_data = request.get_json(silent=True) or {}
    password = request_data.get("password", "")

    current_user = db.session.get(
        User,
        session["user_id"]
    )

    if (
        current_user is None
        or not password
        or not check_password_hash(
            current_user.password_hash,
            password
        )
    ):
        return jsonify({
            "error": "The password you entered is incorrect."
        }), 400

    return jsonify({"verified": True}), 200

@app.route("/api/account/delete", methods=["POST"])
def delete_account():
    # Require both an authenticated session and the account password before
    # permanently removing personal data.
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    current_user_id = session["user_id"]
    current_user = db.session.get(User, current_user_id)
    request_data = request.get_json(silent=True) or {}
    password = request_data.get("password", "")

    if (
        current_user is None
        or not password
        or not check_password_hash(
            current_user.password_hash,
            password
        )
    ):
        return jsonify({
            "error": "The password you entered is incorrect."
        }), 400

    try:
        # Delete dependent records explicitly so every subject, session, goal,
        # and notepad item is removed before the parent User row.
        StudySession.query.filter_by(
            user_id=current_user_id
        ).delete(synchronize_session=False)

        DailyStudyGoal.query.filter_by(
            user_id=current_user_id
        ).delete(synchronize_session=False)

        NotepadItem.query.filter_by(
            user_id=current_user_id
        ).delete(synchronize_session=False)

        Subject.query.filter_by(
            user_id=current_user_id
        ).delete(synchronize_session=False)

        db.session.delete(current_user)
        db.session.commit()

    except Exception:
        # A rollback prevents a partially deleted account if any query fails.
        db.session.rollback()
        app.logger.exception("Failed to permanently delete account")

        return jsonify({
            "error": (
                "Your account could not be deleted. "
                "Please try again."
            )
        }), 500

    session.clear()

    return jsonify({"deleted": True}), 200

@app.route("/subjects")
def manage_subjects():
    # This page serves both first-time onboarding and later account settings.
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user = db.session.get(
        User,
        session["user_id"]
    )

    if current_user is None:
        session.clear()
        return redirect(url_for("login"))

    onboarding = not current_user.subject_setup_completed

    return render_template(
        "subjects.html",
        onboarding=onboarding
    )

@app.route("/api/subjects/complete-setup", methods=["POST"])
def complete_subject_setup():
    # The dashboard remains locked until the user has saved an active subject.
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    current_user_id = session["user_id"]

    if not user_has_active_subjects(current_user_id):
        return jsonify({
            "error": (
                "Please add at least one subject before "
                "continuing to the dashboard."
            )
        }), 400

    current_user = db.session.get(User, current_user_id)
    current_user.subject_setup_completed = True
    db.session.commit()

    return jsonify({"completed": True}), 200

@app.route("/api/subjects", methods=["GET", "POST"])
def subjects_api():
    # GET returns the subject lists; POST validates and creates a new subject.
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    current_user_id = session["user_id"]

    if request.method == "GET":
        # Active subjects are shown first, while inactive subjects are retained
        # so they can be reactivated without losing their analytics history.
        subjects = (
            Subject.query
            .filter_by(user_id=current_user_id)
            .order_by(
                Subject.is_active.desc(),
                Subject.subject_name.asc()
            )
            .all()
        )

        return jsonify({
            "active_subjects": [
                subject_to_dictionary(subject)
                for subject in subjects
                if subject.is_active
            ],
            "inactive_subjects": [
                subject_to_dictionary(subject)
                for subject in subjects
                if not subject.is_active
            ]
        }), 200

    # silent=True converts missing or malformed JSON into None instead of
    # raising an HTML error response; the empty dictionary is then validated.
    request_data = request.get_json(silent=True) or {}

    subject_name = clean_subject_name(
        request_data.get("subject_name", "")
    )

    normalised_name = normalise_subject_name(
        subject_name
    )

    if not subject_name:
        return jsonify({
            "error": "Please enter a subject name."
        }), 400

    if len(subject_name) > 100:
        return jsonify({
            "error": (
                "A subject name cannot exceed "
                "100 characters."
            )
        }), 400

    if normalised_name in RESERVED_SUBJECT_NAMES:
        return jsonify({
            "error": (
                f"{subject_name} is a built-in "
                "analytics category and cannot be "
                "used as a subject name."
            )
        }), 400

    # normalised_name makes spacing and capitalisation variants duplicates.
    existing_subject = Subject.query.filter_by(
        user_id=current_user_id,
        normalised_name=normalised_name
    ).first()

    if existing_subject is not None:
        if existing_subject.is_active:
            error_message = (
                "That subject is already in your "
                "active subjects."
            )
        else:
            error_message = (
                "That subject is in Previous Subjects. "
                "Reactivate it instead."
            )

        return jsonify({
            "error": error_message
        }), 409

    new_subject = Subject(
        user_id=current_user_id,
        subject_name=subject_name,
        normalised_name=normalised_name,
        is_active=True
    )

    try:
        db.session.add(new_subject)
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to create subject")

        return jsonify({
            "error": "The subject could not be saved."
        }), 500

    return jsonify(
        subject_to_dictionary(new_subject)
    ), 201

@app.route(
    "/api/subjects/<int:subject_id>",
    methods=["PATCH", "DELETE"]
)
def subject_api(subject_id):
    # Every lookup includes user_id so one account cannot modify another
    # account's subjects by changing the ID in the request URL.
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    current_user_id = session["user_id"]

    subject = Subject.query.filter_by(
        subject_id=subject_id,
        user_id=current_user_id
    ).first()

    if subject is None:
        return jsonify({
            "error": "Subject not found."
        }), 404

    if request.method == "DELETE":
        try:
            # Permanent deletion keeps the study time but changes affected
            # sessions to NULL, which analytics displays as "Focus".
            StudySession.query.filter_by(
                user_id=current_user_id,
                subject_id=subject.subject_id
            ).update(
                {StudySession.subject_id: None},
                synchronize_session=False
            )

            db.session.delete(subject)
            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception(
                "Failed to permanently delete subject"
            )

            return jsonify({
                "error": (
                    "The subject could not be "
                    "permanently deleted."
                )
            }), 500

        return jsonify({
            "deleted": True,
            "sessions_changed_to_focus": True
        }), 200

    request_data = request.get_json(silent=True) or {}
    action = request_data.get("action")

    # PATCH supports the three non-destructive subject-management operations.
    if action == "rename":
        subject_name = clean_subject_name(
            request_data.get("subject_name", "")
        )

        normalised_name = normalise_subject_name(
            subject_name
        )

        if not subject_name:
            return jsonify({
                "error": "Please enter a subject name."
            }), 400

        if len(subject_name) > 100:
            return jsonify({
                "error": (
                    "A subject name cannot exceed "
                    "100 characters."
                )
            }), 400

        if normalised_name in RESERVED_SUBJECT_NAMES:
            return jsonify({
                "error": (
                    f"{subject_name} is a built-in "
                    "analytics category and cannot be "
                    "used as a subject name."
                )
            }), 400

        duplicate_subject = Subject.query.filter(
            Subject.user_id == current_user_id,
            Subject.normalised_name == normalised_name,
            Subject.subject_id != subject.subject_id
        ).first()

        if duplicate_subject is not None:
            return jsonify({
                "error": (
                    "A subject with that name already "
                    "exists."
                )
            }), 409

        subject.subject_name = subject_name
        subject.normalised_name = normalised_name

    elif action == "deactivate":
        # Deactivation removes a subject from future timer selection while
        # keeping its name and past sessions available to analytics.
        if not subject.is_active:
            return jsonify(
                subject_to_dictionary(subject)
            ), 200

        subject.is_active = False

    elif action == "reactivate":
        subject.is_active = True

    else:
        return jsonify({
            "error": "Invalid subject action."
        }), 400

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to update subject")

        return jsonify({
            "error": "The subject could not be updated."
        }), 500

    return jsonify(
        subject_to_dictionary(subject)
    ), 200

# ---------------------------------------------------------------------------
# MAIN PAGES AND GAMIFIED STUDY TIMER
# ---------------------------------------------------------------------------

@app.route("/home")
def home():
    # The dashboard is available only after authentication and subject setup.
    if "user_id" not in session:
        return redirect(url_for("login"))

    setup_redirect = subject_setup_redirect()
    if setup_redirect is not None:
        return setup_redirect

    # Each fully completed session represents one fully grown tree.
    completed_tree_count = StudySession.query.filter_by(
        user_id=session["user_id"],
        status="completed"
    ).count()

    return render_template(
        "home.html",
        username=session.get("username"),
        completed_tree_count=completed_tree_count
    )

@app.route("/timer")
def timer():
    # Supply only active subjects to the study-session setup dropdown.
    if "user_id" not in session:
        return redirect(url_for("login"))

    setup_redirect = subject_setup_redirect()
    if setup_redirect is not None:
        return setup_redirect

    active_subjects = (
        Subject.query
        .filter_by(
            user_id=session["user_id"],
            is_active=True
        )
        .order_by(Subject.subject_name.asc())
        .all()
    )

    return render_template(
        "timer.html",
        subjects=active_subjects
    )

@app.route("/study-session")
def study_session():
    # Generate all seven tree-stage URLs on the server and pass them to the
    # page, where JavaScript advances the image as study time increases.
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
    # Validate the selected duration and subject, close any stale active
    # session, then create the database record used by the countdown page.
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

    # The timer accepts 15-minute steps from 15 minutes through 12 hours.
    #Validating both the front and backend stops somone from bypassing
    # the interface and submitting invalid data directly.
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

    requested_subject_id = request_data.get("subject_id")
    selected_subject = None

    # A blank subject is valid and becomes the built-in "Focus" category.
    if requested_subject_id not in (None, ""):
        try:
            requested_subject_id = int(
                requested_subject_id
            )

        except (TypeError, ValueError):
            return jsonify({
                "error": "The selected subject is invalid."
            }), 400

        # Ownership and active status are checked on the server rather than
        # trusting the subject options provided by the browser.
        selected_subject = Subject.query.filter_by(
            subject_id=requested_subject_id,
            user_id=session["user_id"],
            is_active=True
        ).first()

        if selected_subject is None:
            return jsonify({
                "error": (
                    "The selected subject is no longer "
                    "available."
                )
            }), 400

    current_time = utc_now()

    # Only one session should be active per user. If an older one remains, save
    # its elapsed time and mark it replaced before starting the new session.
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

        # Clamp recorded time between zero and the session's planned duration.
        old_session.actual_duration_seconds = max(
            0,
            min(
                elapsed_seconds,
                old_session.planned_duration_seconds
            )
        )

        old_session.ended_at = current_time
        old_session.status = "replaced"

    #converts users selected time to seconds
    planned_duration_seconds = duration_minutes * 60

    #CREATES A NEW STUDY SESSION
    new_study_session = StudySession(
        user_id=session["user_id"],
        subject_id=(
            selected_subject.subject_id
            if selected_subject is not None
            else None
        ),
        planned_duration_seconds=(
            planned_duration_seconds
        ),
        actual_duration_seconds=0,
        started_at=current_time,
        status="active"
    )

    db.session.add(new_study_session)
    db.session.commit()

    # Browser-friendly millisecond timestamps let the front end calculate its
    # countdown from a fixed end time instead of relying on interval accuracy.
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
        "end_time_ms": end_time_milliseconds,
        "subject_name": (
            selected_subject.subject_name
            if selected_subject is not None
            else "Focus"
        )
    }), 201

@app.route(
    "/api/study-sessions/<int:study_session_id>/finish",
    methods=["POST"]
)
def finish_study_session(study_session_id):
    # Finalise a completed, manually ended, or navigation-cancelled session and
    # save the actual study time used by the dashboard analytics.
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

    # Confirm ownership even though the record itself was found successfully.
    if (
        study_session_record.user_id
        != session["user_id"]
    ):
        return jsonify({
            "error": "You cannot modify this session."
        }), 403

    # Returning an already-finished record makes repeated finish requests safe.
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
        # A two-second allowance prevents normal network/timer timing
        # differences from rejecting a session at the exact finish point.
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
        # Early finishes save elapsed time but never more than was planned.
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
    # Calculate study time that overlaps one local calendar day. The browser
    # supplies the day boundaries so daylight saving and the user's time zone
    # are handled correctly rather than assumed by the server.
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
        # Clipping each session to the requested boundaries ensures a session
        # crossing midnight contributes only the part studied on this day.
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
    # GET retrieves the selected date's goal; POST creates or updates it.
    # Goals use the same 15-minute limits as the study-session timer.
    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    if request.method == "GET":
        # Parse the ISO date sent by the dashboard into a Python date used by
        # the DailyStudyGoal model's unique user/date record.
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

    # Update the existing row when present so a user has only one goal per day.
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
    # Build both dashboard charts from the same monthly study data:
    # 1. total study seconds for every day in the selected month;
    # 2. total study seconds grouped by subject for the doughnut chart.
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

    # A month contains 28-31 days, so its boundary list contains 29-32 values.
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

    # Strictly increasing boundaries prevent negative or overlapping day spans.
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

    # Convert browser-provided local midnights into UTC-naive datetimes to
    # match how timestamps are stored by SQLite in this project.
    utc_boundaries = [
        datetime.fromtimestamp(
            boundary / 1000,
            tz=timezone.utc
        ).replace(tzinfo=None)
        for boundary in day_boundaries_ms
    ]

    month_start = utc_boundaries[0]
    month_end = utc_boundaries[-1]

    # Include every session with recorded study time, not only sessions whose
    # status is "completed". This preserves useful early-finish study data.
    study_session_records = StudySession.query.filter(
        StudySession.user_id == session["user_id"],
        StudySession.actual_duration_seconds > 0,
        StudySession.started_at < month_end
    ).all()

    # One total is maintained for each gap between consecutive boundaries.
    daily_seconds = [
        0 for _ in range(len(utc_boundaries) - 1)
    ]

    subject_seconds = {}

    for study_record in study_session_records:
        # Recreate the effective end time from the recorded actual duration.
        session_start = study_record.started_at

        session_end = (
            study_record.started_at
            + timedelta(
                seconds=study_record.actual_duration_seconds
            )
        )

        # Sessions ending before this month cannot contribute to either chart.
        if session_end <= month_start:
            continue

        month_overlap_start = max(
            session_start,
            month_start
        )

        month_overlap_end = min(
            session_end,
            month_end
        )

        if month_overlap_end > month_overlap_start:
            # NULL subject IDs include older and uncategorised sessions and are
            # intentionally grouped into the built-in Focus category.
            subject_name = (
                study_record.subject.subject_name
                if study_record.subject is not None
                else "Focus"
            )

            subject_seconds[subject_name] = (
                subject_seconds.get(subject_name, 0)
                + int((
                    month_overlap_end
                    - month_overlap_start
                ).total_seconds())
            )

        # Split sessions at day boundaries. This correctly distributes a
        # session that crosses midnight across both daily columns.
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

    # Rank subjects by longest duration, using the name only as a stable tie
    # breaker so chart ordering remains predictable.
    ordered_subjects = sorted(
        subject_seconds.items(),
        key=lambda item: (
            -item[1],
            item[0].casefold()
        )
    )

    # Keep the six largest categories readable and combine all smaller
    # categories into a single "Other" slice.
    displayed_subjects = ordered_subjects[:6]
    remaining_subject_seconds = sum(
        seconds
        for _, seconds in ordered_subjects[6:]
    )

    if remaining_subject_seconds > 0:
        displayed_subjects.append((
            "Other",
            remaining_subject_seconds
        ))

    return jsonify({
        "daily_seconds": daily_seconds,
        "subject_labels": [
            subject_name
            for subject_name, _ in displayed_subjects
        ],
        "subject_seconds": [
            seconds
            for _, seconds in displayed_subjects
        ],
        "subject_total_seconds": sum(
            subject_seconds.values()
        )
    }), 200

@app.route("/calendar")
def calendar():
    # Render the protected calendar page. Its interactive behaviour is handled
    # by the corresponding template and front-end scripts.
    if "user_id" not in session:
        return redirect(url_for("login"))

    setup_redirect = subject_setup_redirect()
    if setup_redirect is not None:
        return setup_redirect

    return render_template("calendar.html")

@app.route("/users")
def users():
    # Development-only listing of the user records currently in the database.
    all_users = User.query.all()

    if not all_users:
        return "No users found."

    return "<br>".join(
        [f"{user.user_id} - {user.username} - {user.user_email}" for user in all_users]
    )

def notepad_item_to_dictionary(item):
    """
    Convert a NotepadItem database object into data that
    can be returned to JavaScript as JSON.
    """
    return {
        "id": item.notepad_item_id,
        "text": item.item_text
    }

# ---------------------------------------------------------------------------
# USER-SPECIFIC NOTEPAD API
# ---------------------------------------------------------------------------

@app.route("/api/notepad-items", methods=["GET", "POST"])
def notepad_items_api():
    """
    GET:
        Return all notepad items belonging to the signed-in user.




    POST:
        Create a new notepad item for the signed-in user.
    """

    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    current_user_id = session["user_id"]

    if request.method == "GET":
        # Filtering by user_id keeps each account's notes private. Primary-key
        # order preserves the order in which items were created.
        items = (
            NotepadItem.query
            .filter_by(user_id=current_user_id)
            .order_by(NotepadItem.notepad_item_id.asc())
            .all()
        )

        return jsonify({
            "items": [
                notepad_item_to_dictionary(item)
                for item in items
            ]
        })

    # POST validates and trims the note before storing it.
    data = request.get_json(silent=True) or {}
    item_text = data.get("text", "")

    if not isinstance(item_text, str):
        return jsonify({
            "error": "The item text must be text."
        }), 400

    item_text = item_text.strip()

    if not item_text:
        return jsonify({
            "error": "A notepad item cannot be empty."
        }), 400

    if len(item_text) > 1000:
        return jsonify({
            "error": "A notepad item cannot exceed 1000 characters."
        }), 400

    new_item = NotepadItem(
        user_id=current_user_id,
        item_text=item_text
    )

    try:
        db.session.add(new_item)
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to create notepad item")

        return jsonify({
            "error": "The item could not be saved."
        }), 500

    return jsonify(
        notepad_item_to_dictionary(new_item)
    ), 201

@app.route(
    "/api/notepad-items/<int:item_id>",
    methods=["PATCH", "DELETE"]
)
def notepad_item_api(item_id):
    """
    PATCH:
        Edit an item belonging to the signed-in user.
        Delete it if the edited text is empty.

    DELETE:
        Delete an item belonging to the signed-in user.
    """

    if "user_id" not in session:
        return jsonify({
            "error": "You must be logged in."
        }), 401

    current_user_id = session["user_id"]

    # Fetch by both item ID and current user ID to enforce record ownership.
    item = NotepadItem.query.filter_by(
        notepad_item_id=item_id,
        user_id=current_user_id
    ).first()

    if item is None:
        return jsonify({
            "error": "Notepad item not found."
        }), 404

    if request.method == "DELETE":
        # An explicit DELETE removes the selected item permanently.
        try:
            db.session.delete(item)
            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception("Failed to delete notepad item")

            return jsonify({
                "error": "The item could not be deleted."
            }), 500

        return jsonify({
            "deleted": True
        })

    data = request.get_json(silent=True) or {}
    updated_text = data.get("text", "")

    if not isinstance(updated_text, str):
        return jsonify({
            "error": "The item text must be text."
        }), 400

    updated_text = updated_text.strip()

    # Treating an empty edit as deletion keeps blank rows out of the database.
    if not updated_text:
        try:
            db.session.delete(item)
            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception(
                "Failed to delete empty notepad item"
            )
            return jsonify({
                "error": "The empty item could not be deleted."
            }), 500

        return jsonify({
            "deleted": True
        })

    if len(updated_text) > 1000:
        return jsonify({
            "error": "A notepad item cannot exceed 1000 characters."
        }), 400

    # A non-empty PATCH replaces the stored text of the existing item.
    item.item_text = updated_text

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to update notepad item")

        return jsonify({
            "error": "The item could not be updated."
        }), 500

    return jsonify(
        notepad_item_to_dictionary(item)
    )

if __name__ == "__main__":
    # Run Flask's development server only when this file is launched directly.
    app.run(debug=False)

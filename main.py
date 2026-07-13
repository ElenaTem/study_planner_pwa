import os
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash
from database_manager import db, User

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FOLDER = os.path.join(BASE_DIR, ".database")
DATABASE_PATH = os.path.join(DB_FOLDER, "study_planner.db")

# Checks if the database folder exists
os.makedirs(DB_FOLDER, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key"

db.init_app(app)

with app.app_context():
    db.create_all()

print("Using database file:", DATABASE_PATH)


@app.route("/")
def index():
    return redirect(url_for("register"))

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user_email = request.form.get("user_email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not user_email or not password:
            return render_template("register.html", error="Please fill in all fields.")

        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters long.")

        existing_user = User.query.filter(
            (User.username == username) | (User.user_email == user_email)
        ).first()

        if existing_user:
            return render_template("register.html", error="Username or email already exists.")

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        new_user = User(
            username=username,
            user_email=user_email,
            password_hash=password_hash
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/users")
def users():
    all_users = User.query.all()

    if not all_users:
        return "No users found."

    return "<br>".join(
        [f"{user.user_id} - {user.username} - {user.user_email}" for user in all_users]
    )


@app.route("/timer")
def timer():
    return render_template("timer.html")


@app.route("/calendar")
def calendar():
    return render_template("calendar.html")

if __name__ == "__main__":
    app.run(debug=True)




'''from flask import Flask, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash
from database_manager import db, User

app = Flask(__name__, instance_relative_config=True)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///study_planner.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key"

db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        user_email = request.form.get("user_email")
        password = request.form.get("password")

        # Check for empty inputs
        if not username or not user_email or not password:
            return "Please fill in all fields."

        # Check password length
        if len(password) < 8:
            return "Password must be at least 8 characters long."

        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.user_email == user_email)
        ).first()

        if existing_user:
            return "Username or email already exists."

        # Hash the password
        password_hash = generate_password_hash(password)

        # Create new user
        new_user = User(
            username=username,
            user_email=user_email,
            password_hash=password_hash
        )

        # Save to database
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("home"))

    return render_template("register.html")

@app.route("/users")
def users():
    all_users = User.query.all()
    return "<br>".join(
        [f"{user.user_id} - {user.username} - {user.user_email}" for user in all_users]
    )

if __name__ == "__main__":
    app.run(debug=True)'''
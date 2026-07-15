import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database_manager import db, User

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


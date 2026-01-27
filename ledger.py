from flask import Flask, render_template,session , request
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required
import sqlite3

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/")
#@login_required
def index():
    # Renders the 'index.html' file from the templates folder
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("/login.html")

@app.route("/dashboard")
def dashboard():
    #todo
    return render_template("/dashboard.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        name = request.form.get("username")
        if not name:
            return apology("username must be provided", 400)

        password = request.form.get("password")
        if not password:
            return apology("must provide password", 400)

        confirmation = request.form.get("confirmation")
        if not confirmation or (confirmation != password):
            return apology("please provide confirmation or it is not same", 400)

        # Check if username is taken
        rows = db.execute("SELECT * FROM users WHERE username = ?", (name,))
        if len(rows) > 0:
            return apology("username is already taken", 400)

        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?)", (name,password_hash))

        user_id = db.execute("SELECT id FROM users WHERE username = ?", (name,))[0]["id"]

        session["user_id"] = user_id

        return redirect("/")
    else:
        return render_template("/register.html")

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current")
        new = request.form.get("new")
        confirm = request.form.get("confirm")

        if not current or not new or not confirm:
            return apology("must fill all fields", 403)

        if new != confirm:
            return apology("new passwords do not match", 403)

        user = db.execute("SELECT hash FROM users WHERE id = ?", (session["user_id"],))[0]
        if not check_password_hash(user["hash"], current):
            return apology("incorrect current password", 403)

        new_hash = generate_password_hash(new)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", (new_hash, session["user_id"]))

        flash("Password updated successfully!")
        return redirect("/")

    return render_template("change_password.html")


if __name__ == "__main__":
    app.run(debug=True)

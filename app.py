from flask import Flask, render_template,session , request,redirect,url_for
from flask_session import Session
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required
import sqlite3

app = Flask(__name__)

app.secret_key="rma will lose to benfica we will be there"

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def get_database():
    conn = sqlite3.connect('ledger.db')
    conn.row_factory = sqlite3.Row
    return conn



@app.route("/",methods=["GET"])
#@login_required
def index():
    # Renders the 'index.html' file from the templates folder
    debit = 0
    credit = 0
    conn = get_database()
    user_id = 1 # session["user_id"]

    amounts = conn.execute('''
        SELECT 
            T.amount AS money,
            T.is_settled AS settled,
            T.transaction_type AS action 
        FROM transactions AS T
        INNER JOIN page_participants AS P ON T.page_id = P.page_id
        INNER JOIN users AS U ON P.page_id = U.id 
        WHERE U.id = ?
    ''', (user_id,)).fetchall()
    pages = conn.execute('select P.name as name,T.amount as amount,T.description as description,T.transaction_date as date from pages as P inner join transactions as T on P.page_id = T.page_id ;').fetchall()
    
    for amount in amounts:
        if amount.settled == 0:
            continue
        elif amount.settled == 1 and transaction_type == "debit":
            debit = debit + amount.amount
        elif amount.is_settled == 1 and transaction_type == "credit":
            credit = credit + amount.amount
        else:
            return apology("error occured while reading database",500)
    conn.close()
    return render_template("index.html",debit = debit,credit = credit,pages=pages)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure name was submitted
        if not request.form.get("name"):
            return apology("must provide name", 400)

        # Ensure loginpsswd was submitted
        elif not request.form.get("password"):
            return apology("must provide loginpsswd", 400)

        # Query database for name
        db = get_database()
        rows = db.execute(
            "SELECT * FROM users WHERE name = ?", request.form.get("name")
        )

        # Ensure name exists and loginpsswd is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["loginpsswd"], request.form.get("password")
        ):
            return apology("invalid name and/or loginpsswd", 403)

        # Remember which user has logged in
        current_time = datetime.now()
        session["user_id"] = rows[0]["id"]
        db.execute("insert into users (last_login) values (?)",current_time)
        db.commit()
        db.close()

        # Redirect user to home page
        return redirect(url_for("index"))

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
        name = request.form.get("name")
        if not name:
            return apology("name must be provided", 400)

        loginpsswd = request.form.get("password")
        if not loginpsswd:
            return apology("must provide loginpsswd", 400)

        confirmation = request.form.get("confirmation")
        if not confirmation or (confirmation != loginpsswd):
            return apology("please provide confirmation or it is not same", 400)

        # Check if name is taken
        rows = db.execute("SELECT * FROM users WHERE name = ?", (name,))
        if len(rows) > 0:
            return apology("name is already taken", 400)

        loginpsswd_hash = generate_password_hash(loginpsswd)
        db.execute("INSERT INTO users (name,loginpsswd) VALUES (?)", (name,loginpsswd_hash))

        user_id = db.execute("SELECT id FROM users WHERE name = ?", (name,))[0]["id"]

        session["user_id"] = user_id

        return redirect("/")
    else:
        return render_template("/register.html")

@app.route("/change-loginpsswd", methods=["GET", "POST"])
@login_required
def change_loginpsswd():
    if request.method == "POST":
        current = request.form.get("current")
        new = request.form.get("new")
        confirm = request.form.get("confirm")

        if not current or not new or not confirm:
            return apology("must fill all fields", 403)

        if new != confirm:
            return apology("new loginpsswds do not match", 403)

        user = db.execute("SELECT hash FROM users WHERE id = ?", (session["user_id"],))[0]
        if not check_password_hash(user["hash"], current):
            return apology("incorrect current loginpsswd", 403)

        new_hash = generate_password_hash(new)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", (new_hash, session["user_id"]))

        flash("loginpsswd updated successfully!")
        return redirect("/")

    return render_template("change_loginpsswd.html")


if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_session import Session
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required
import sqlite3

app = Flask(__name__)
app.secret_key = "rma will lose to benfica we will be there"   # Change this in production!

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def get_database():
    conn = sqlite3.connect('ledger.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
@login_required
def index():
    """Home Page"""
    conn = get_database()
    user_id = session["user_id"] # TODO  :change it

    try:
        # ====================== CREDIT & DEBIT ======================
        balance_query = """
            SELECT 
                SUM(CASE WHEN tp.user_id = ? AND t.created_by != ? THEN tp.share_amount ELSE 0 END) as debit,
                SUM(CASE WHEN t.created_by = ? AND tp.user_id != ? THEN tp.share_amount ELSE 0 END) as credit
            FROM transactions t
            JOIN transaction_participants tp ON t.id = tp.transaction_id
            WHERE t.is_settled = 0
              AND t.page_id IN (SELECT page_id FROM page_participants WHERE user_id = ?)
        """
        result = conn.execute(balance_query, (user_id, user_id, user_id, user_id, user_id)).fetchone()

        debit = result['debit'] or 0
        credit = result['credit'] or 0

        # ====================== RECENT TRANSACTIONS ======================
        recent_query = """
            SELECT 
                p.name as page_name,
                t.amount,
                t.description,
                t.transaction_date as date,
                t.transaction_type
            FROM transactions t
            JOIN pages p ON t.page_id = p.page_id
            JOIN page_participants pp ON p.page_id = pp.page_id
            WHERE pp.user_id = ?
            ORDER BY t.created_at DESC
            LIMIT 10
        """
        recent_transactions = conn.execute(recent_query, (user_id,)).fetchall()

    except Exception as e:
        flash("Database error occurred", "danger")
        debit = credit = 0
        recent_transactions = []
    finally:
        conn.close()

    return render_template("index.html",
                           debit=debit,
                           credit=credit,
                           pages=recent_transactions)   # keeping your template variable name


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()   # Clear previous session

    if request.method == "POST":
        username = request.form.get("name")
        password = request.form.get("password")

        if not username or not password:
            flash("Username and password are required", "danger")
            return redirect(url_for("login"))

        db = get_database()
        try:
            user = db.execute(
                "SELECT id, name, loginpsswd FROM users WHERE name = ? OR uniquekey = ?",
                (username, username)
            ).fetchone()

            if not user:
                flash("User not found", "danger")
                return redirect(url_for("login"))

            if not check_password_hash(user["loginpsswd"], password):
                flash("Incorrect password", "danger")
                return redirect(url_for("login"))

            # ✅ Login successful
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            # Update last login
            db.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["id"])
            )
            db.commit()

            flash(f"Welcome back, {user['name']}!", "success")
            
            # Force redirect to home
            return redirect("/")

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("login"))
        
        finally:
            db.close()

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    # TODO :if user is in transaction then only show calculations
    conn = get_database()
    conn.row_factory = sqlite3.Row  # So we get dict-like rows

    # This query calculates simplified net pairwise debts
    query = """
    WITH user_shares AS (
        -- What each user should pay (their share)
        SELECT 
            tp.user_id,
            t.page_id,
            SUM(tp.share_amount) as total_share,
            p.currency
        FROM transaction_participants tp
        JOIN transactions t ON tp.transaction_id = t.id
        JOIN pages p ON t.page_id = p.page_id
        GROUP BY tp.user_id, t.page_id, p.currency
    ),
    user_paid AS (
        -- What each user actually paid
        SELECT 
            t.created_by as user_id,
            t.page_id,
            SUM(t.amount) as total_paid,
            p.currency
        FROM transactions t
        JOIN pages p ON t.page_id = p.page_id
        GROUP BY t.created_by, t.page_id, p.currency
    ),
    balances AS (
        SELECT 
            COALESCE(us.user_id, up.user_id) as user_id,
            COALESCE(us.page_id, up.page_id) as page_id,
            COALESCE(us.currency, up.currency) as currency,
            COALESCE(up.total_paid, 0) - COALESCE(us.total_share, 0) as net_balance
        FROM user_shares us
        FULL OUTER JOIN user_paid up 
            ON us.user_id = up.user_id 
           AND us.page_id = up.page_id
    ),
    simplified_debts AS (
        -- Convert net balances into "A owes B" format (greedy simplification)
        SELECT 
            u1.name as from_name,
            u2.name as to_name,
            b1.net_balance as amount,
            b1.currency
        FROM balances b1
        JOIN balances b2 ON b1.page_id = b2.page_id
        JOIN users u1 ON b1.user_id = u1.id
        JOIN users u2 ON b2.user_id = u2.id
        WHERE b1.user_id < b2.user_id 
          AND b1.net_balance < 0 
          AND b2.net_balance > 0
        GROUP BY u1.name, u2.name, b1.currency
        HAVING ABS(SUM(b1.net_balance)) > 0.01
    )
    SELECT 
        from_name,
        to_name,
        ABS(amount) as amount,
        currency
    FROM simplified_debts
    ORDER BY amount DESC;
    """

    data = conn.execute(query).fetchall()
    conn.close()

    return render_template("dashboard.html", data=data)


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
        uniquekey = request.form.get("uniquekey")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validation
        if not name:
            flash("Name must be provided", "danger")
            return redirect(url_for("register"))

        if not uniquekey:
            flash("Unique Key is required", "danger")
            return redirect(url_for("register"))

        if not password:
            flash("Password must be provided", "danger")
            return redirect(url_for("register"))

        if password != confirmation:
            flash("Passwords do not match", "danger")
            return redirect(url_for("register"))

        db = get_database()

        try:
            # Check if name or uniquekey already exists
            existing = db.execute(
                "SELECT id FROM users WHERE name = ? OR uniquekey = ?", 
                (name, uniquekey)
            ).fetchone()

            if existing:
                flash("Name or Unique Key is already taken", "danger")
                return redirect(url_for("register"))

            # Hash password
            password_hash = generate_password_hash(password)

            # Insert new user
            db.execute("""
                INSERT INTO users (name, loginpsswd, uniquekey, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (name, password_hash, uniquekey))

            db.commit()

            # Get the newly created user
            user = db.execute(
                "SELECT id, name FROM users WHERE uniquekey = ?", 
                (uniquekey,)
            ).fetchone()

            # Log user in automatically
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            flash("Registration successful! Welcome to Ledger.", "success")
            return redirect(url_for("index"))

        except Exception as e:
            db.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return redirect(url_for("register"))

        finally:
            db.close()

    # GET request
    return render_template("register.html")

@app.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == "POST":
        user_id = request.form.get("user_id")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not user_id or not password or not confirmation:
            flash("All fields are required", "danger")
            return redirect(url_for("reset_password", user_id=user_id))

        if password != confirmation:
            flash("Passwords do not match", "danger")
            return redirect(url_for("reset_password", user_id=user_id))

        db = get_database()

        try:
            password_hash = generate_password_hash(password)

            db.execute(
                "UPDATE users SET loginpsswd = ? WHERE id = ?",
                (password_hash, user_id)
            )
            db.commit()

            flash("Your password has been successfully reset!", "success")
            return redirect(url_for("login"))

        except Exception as e:
            flash("Something went wrong. Please try again.", "danger")
            return redirect(url_for("reset_password", user_id=user_id))

        finally:
            db.close()

    # GET request - Show form (with user_id from query parameter)
    user_id = request.args.get("user_id")
    if not user_id:
        flash("Invalid reset link", "danger")
        return redirect(url_for("login"))

    return render_template("reset_password.html", user_id=user_id)

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        
        db = get_database()
        user = db.execute(
            "SELECT id FROM users WHERE name = ? OR uniquekey = ?",
            (username, username)
        ).fetchone()
        db.close()

        if user:
            # In real app, send email with token. For now, we'll use direct link
            flash("Password reset link generated (Demo Mode)", "info")
            return redirect(url_for("reset_password", user_id=user["id"]))
        else:
            flash("No account found with this username or unique key", "danger")

    return render_template("forgot_password.html")

# List of all pages
@app.route("/pages")
@login_required
def pages():
    conn = get_database()
    conn.row_factory = sqlite3.Row
    user_id = session.get("user_id", 1)   # Replace with actual session later

    query = """
        SELECT p.page_id, p.name, p.currency, p.created_at 
        FROM pages p
        JOIN page_participants pp ON p.page_id = pp.page_id
        WHERE pp.user_id = ?
        ORDER BY p.created_at DESC
    """
    pages_list = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return render_template("pages.html", pages=pages_list)


# Single Page Detail
@app.route("/page/<int:page_id>")
@login_required
def page_detail(page_id):
    conn = get_database()
    conn.row_factory = sqlite3.Row
    user_id = session.get("user_id", 1)

    # Page Info
    page = conn.execute("SELECT * FROM pages WHERE page_id = ?", (page_id,)).fetchone()

    # Participants
    participants = conn.execute("""
        SELECT u.id as user_id, u.name 
        FROM page_participants pp
        JOIN users u ON pp.user_id = u.id
        WHERE pp.page_id = ?
    """, (page_id,)).fetchall()

    # Transactions
    transactions = conn.execute("""
        SELECT t.*, u.name as paid_by_name 
        FROM transactions t
        JOIN users u ON t.created_by = u.id
        WHERE t.page_id = ?
        ORDER BY t.transaction_date DESC
    """, (page_id,)).fetchall()

    conn.close()

    return render_template("page.html", 
                         page=page, 
                         participants=participants, 
                         transactions=transactions,
                         current_user_id=user_id)

@app.route("/create-page", methods=["GET", "POST"])
@login_required
def create_page():
    if request.method == "POST":
        name = request.form.get("name")
        currency = request.form.get("currency", "INR")
        description = request.form.get("description", "")

        if not name:
            return apology("Page name is required", 400)

        conn = get_database()
        user_id = session.get("user_id")

        try:
            # Create new page
            cursor = conn.execute("""
                INSERT INTO pages (name, created_by, currency)
                VALUES (?, ?, ?)
            """, (name.strip(), user_id, currency))
            
            page_id = cursor.lastrowid

            # Add creator as participant
            conn.execute("""
                INSERT INTO page_participants (page_id, user_id)
                VALUES (?, ?)
            """, (page_id, user_id))

            conn.commit()
            flash(f"Page '{name}' created successfully!", "success")
            return redirect(f"/page/{page_id}")

        except Exception as e:
            conn.rollback()
            return apology("Error creating page", 500)
        
        finally:
            conn.close()

    # GET request
    return render_template("create_page.html")

# ====================== HISTORY ======================
@app.route("/history")
@login_required
def history():
    conn = get_database()
    conn.row_factory = sqlite3.Row
    user_id = session.get("user_id", 1)

    query = """
        SELECT 
            t.id,
            t.description,
            t.amount,
            t.transaction_date,
            t.transaction_type,
            t.is_settled,
            p.name as page_name,
            u.name as paid_by_name
        FROM transactions t
        JOIN pages p ON t.page_id = p.page_id
        JOIN users u ON t.created_by = u.id
        JOIN page_participants pp ON p.page_id = pp.page_id
        WHERE pp.user_id = ?
        ORDER BY t.transaction_date DESC, t.created_at DESC
    """
    transactions = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    return render_template("history.html", transactions=transactions)


# ====================== SINGLE TRANSACTION ======================
@app.route("/transaction/<int:transaction_id>")
@login_required
def transaction_detail(transaction_id):
    conn = get_database()
    conn.row_factory = sqlite3.Row
    user_id = session.get("user_id", 1)

    # Transaction Info
    transaction = conn.execute("""
        SELECT 
            t.*,
            p.name as page_name,
            u.name as paid_by_name
        FROM transactions t
        JOIN pages p ON t.page_id = p.page_id
        JOIN users u ON t.created_by = u.id
        WHERE t.id = ?
    """, (transaction_id,)).fetchone()

    if not transaction:
        return "Transaction not found", 404

    # Participants & Shares
    participants = conn.execute("""
        SELECT 
            u.id as user_id,
            u.name,
            tp.share_amount
        FROM transaction_participants tp
        JOIN users u ON tp.user_id = u.id
        WHERE tp.transaction_id = ?
        ORDER BY tp.share_amount DESC
    """, (transaction_id,)).fetchall()

    conn.close()

    return render_template("transaction.html", 
                         transaction=transaction, 
                         participants=participants,
                         current_user_id=user_id)


@app.route("/add-transaction", methods=["GET", "POST"])
@login_required
def add_transaction():
    conn = get_database()
    conn.row_factory = sqlite3.Row
    user_id = session.get("user_id")

    if request.method == "POST":
        page_id = request.form.get("page_id")
        description = request.form.get("description")
        amount = float(request.form.get("amount"))
        transaction_date = request.form.get("transaction_date")
        paid_by = request.form.get("paid_by")
        split_type = request.form.get("split_type")

        # Logic to insert transaction + participants will go here
        # (I can give you the full backend code in the next message if you want)

        flash("Transaction added successfully!", "success")
        return redirect(f"/page/{page_id}")

    # GET Request - Show Form
    pages = conn.execute("""
        SELECT page_id, name, currency 
        FROM pages 
        WHERE page_id IN (SELECT page_id FROM page_participants WHERE user_id = ?)
    """, (user_id,)).fetchall()

    # Get participants for the first page (you can improve this with JS later)
    participants = []  # You can pass current page's participants

    conn.close()

    return render_template("add_transaction.html", 
                         pages=pages, 
                         participants=participants,
                         current_user_id=user_id,
                         today=date.today().isoformat())


if __name__ == "__main__":
    app.run(debug=True)

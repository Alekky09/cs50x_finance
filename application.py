import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    shares = db.execute("SELECT shares, SUM(num_of_shares) FROM purchases JOIN users ON purchases.user_id=users.id WHERE users.id = :session_id GROUP BY purchases.shares", session_id = session["user_id"])

    share_list = []

    total = 0

    for row in shares:

        list_row = {}
        x = row["shares"]
        share = lookup(x)["symbol"]
        share_name = lookup(x)["name"]
        share_price = lookup(x)["price"]
        owned_shares = db.execute("SELECT SUM(num_of_shares) FROM purchases JOIN users ON purchases.user_id=users.id WHERE users.id = :session_id AND purchases.shares = :share", session_id = session["user_id"], share = x)[0]["SUM(num_of_shares)"]
        owned_value = owned_shares*share_price

        total += owned_value

        list_row["share"] = share
        list_row["share_name"] = share_name
        list_row["share_price"] = round(share_price, 2)
        list_row["owned_shares"] = owned_shares
        list_row["owned_value"] = round(owned_value, 2)

        if owned_shares != 0:

            share_list.append(list_row)

    users_credit = round((db.execute("SELECT cash FROM users WHERE id = :session_id", session_id = session["user_id"])[0]["cash"]), 2)
    return render_template("index.html", rows = share_list, cash = users_credit, total = round(total, 2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol = lookup(request.form.get("symbol"))["symbol"]

        share_n = request.form.get("shares", type=int)

        rows = lookup(symbol)

        if share_n < 0 or not share_n:

            return apology("please provide a positive number", 403)

        if not symbol:

            return apology("please provide a valid share symbol", 403)

        users_credit = float(db.execute("SELECT cash FROM users WHERE id = :session_id", session_id = session["user_id"])[0]["cash"])

        share_price = lookup(symbol)["price"]

        total_price = round(share_price * share_n, 2)

        if users_credit < total_price:

            return apology("Insufficient funds", 403)

        else:

            db.execute("UPDATE users SET cash= :cash WHERE id= :session_id", cash= users_credit - total_price, session_id = session["user_id"])

            db.execute("INSERT INTO purchases (user_id, shares, num_of_shares, at_price, time) VALUES(:session_id, :symbol, :share_n, :share_price, CURRENT_TIMESTAMP)", session_id = session["user_id"], symbol = symbol, share_n = share_n, share_price = share_price)



        return render_template("buy.html", rows = rows)
    else:
        return render_template("buy.html", rows = None)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    shares = db.execute("SELECT shares, num_of_shares, at_price, time FROM purchases JOIN users ON purchases.user_id=users.id WHERE users.id = :session_id", session_id = session["user_id"])

    return render_template("history.html", rows = shares)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        symbol = request.form.get("symbol")

        row = lookup(symbol)
        if not row:
            return render_template("quote.html")
        return render_template("quoted.html", row = row)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    def sh_apology(x):

        return apology("must provide " + x, 403)

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        names = db.execute("SELECT username FROM users WHERE username = :username",
                          username=username)

        # Ensure username was submitted
        if not username:
            return sh_apology("username")

        elif names:
            return sh_apology("a genuine username")

        # Ensure password was submitted
        elif not password:
            return sh_apology("password")

        elif not confirmation:
            return sh_apology("confirmation")

        elif confirmation != password:
            return apology("passwords dont match", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashpw)", username = username, hashpw= generate_password_hash(password))

        return redirect("/")



    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    shares = db.execute("SELECT shares, SUM(num_of_shares) FROM purchases JOIN users ON purchases.user_id=users.id WHERE users.id = :session_id GROUP BY purchases.shares", session_id = session["user_id"])

    share_list = []

    for row in shares:
        list_row = {}

        share = lookup(row["shares"])["symbol"]
        owned_shares = row["SUM(num_of_shares)"]


        list_row["share"] = share
        list_row["owned_shares"] = owned_shares

        if owned_shares != 0:
            share_list.append(list_row)

    print(share_list)



    if request.method == "POST":

        symbol = request.form.get("symbol")

        share_n = request.form.get("shares", type=int)

        share_price = lookup(symbol)["price"]

        total_price = share_n * share_price

        users_credit = float(db.execute("SELECT cash FROM users WHERE id = :session_id", session_id = session["user_id"])[0]["cash"])


        if share_n < 0:
            return apology("Please provide valid number")

        for row in share_list:

            if row["share"] == symbol and share_n > row["owned_shares"]:

                return apology("You dont have enough shares")



        db.execute("UPDATE users SET cash= :cash WHERE id= :session_id", cash= users_credit + total_price, session_id = session["user_id"])

        db.execute("INSERT INTO purchases (user_id, shares, num_of_shares, at_price, time) VALUES(:session_id, :symbol, :share_n, :share_price, CURRENT_TIMESTAMP)", session_id = session["user_id"], symbol = symbol, share_n = -share_n, share_price = share_price)



    return render_template("sell.html", rows = share_list)







def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

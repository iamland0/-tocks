import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
# usd is a function (defined in helpers.py) that will make it easier to format values as US dollars (USD).
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem i.e., disk (instead of digitally signed cookies which is Flask default)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
# @login_required (a function defined in helpers.py) is a decorator that ensures, if a user tries to visit this route, they will first be redirected to login so as to log in.
@login_required
def index():
    """Show portfolio of stocks"""
    # Lando was here...
    # Get the user's current cash, portfolio, and name from database
    portfolio_db = db.execute("SELECT owned_symbol, owned_shares FROM owned WHERE owned_id = ?", session["user_id"])
    users_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    username_db = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    username = username_db[0]["username"].capitalize()
    # Get the user's cash
    cash = users_cash[0]["cash"]
    # Create an empty list
    portfolio = []
    # Create a total variable to keep track the total price of all shares the user's owned
    total = 0

    if len(portfolio_db) > 0:

        for i in range(len(portfolio_db)):
            # Make a portfolio dictionary
            portfolio_dict = {}
            #  Get the stock's symbol (eg: nflx)
            portfolio_dict["symbol"] = portfolio_db[i]["owned_symbol"]
            # Get the name of the stock's symbol (eg: NetFlix Inc)
            portfolio_dict["name"] = lookup(portfolio_dict["symbol"])["name"]
            # Get the amount of shares owned
            portfolio_dict["shares"] = portfolio_db[i]["owned_shares"]
            # Get the current price and convert it to US Dollars format
            portfolio_dict["price"] = lookup(portfolio_dict["symbol"])["price"]
            # Get the total price for each share
            portfolio_dict["total_each"] = lookup(portfolio_dict["symbol"])["price"] * portfolio_dict["shares"]
            # Keep track of the total price of all shares owned
            total += lookup(portfolio_dict["symbol"])["price"] * portfolio_dict["shares"]
            # Store it to the portfolio list
            portfolio.append(portfolio_dict)

        # Add users current cash to total
        total += users_cash[0]["cash"]

    return render_template("index.html", portfolios=portfolio, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Lando was here...
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        symbol_exist = lookup(symbol)
        # Check symbol and shares
        if not symbol:
            return apology("missing symbol")
        elif symbol_exist == None:
            return apology("invalid symbol")
        elif not shares or not shares.isdigit():
            return apology("invalid shares")

        shares = int(request.form.get("shares"))
        if shares < 0:
            return apology("invalid shares")

        # Check the stock current price
        current_price = symbol_exist["price"]
        users_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Check if user's cash is enough, substract it if enough. Then update the user's cash in database
        if users_cash[0]["cash"] < current_price * shares:
            return apology("you're too broke", 707)
        users_cash[0]["cash"] -= current_price * shares
        db.execute("UPDATE users SET cash = ? WHERE id = ?", users_cash[0]["cash"], session["user_id"])

        #  Get data from the database
        purchases_date = db.execute("SELECT datetime()")
        owned_stocks = db.execute("SELECT owned_symbol, owned_shares FROM owned WHERE owned_id = ?", session["user_id"])

        # Check if the user's already have that stock
        check = False
        for i in range(len(owned_stocks)):
            if symbol_exist["symbol"] in owned_stocks[i]["owned_symbol"]:
                check = True
                break

        # Update if the user has that stock, otherwise insert
        if check:
            owned_symbol = db.execute("SELECT owned_symbol, owned_shares FROM owned WHERE owned_symbol = ? AND owned_id = ?",
                                      symbol_exist["symbol"], session["user_id"])
            db.execute("UPDATE owned SET owned_shares = ? WHERE owned_symbol = ? AND owned_id = ?",
                       owned_symbol[0]["owned_shares"] + shares, symbol_exist["symbol"], session["user_id"])
        else:
            db.execute("INSERT INTO owned(owned_id, owned_symbol, owned_shares) VALUES(?, ?, ?)",
                       session["user_id"], symbol_exist["symbol"], shares)

        # Insert to other database to keep track of the user purchase history
        db.execute("INSERT INTO purchases(purchases_id, symbol, shares, price, purchases_date) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], symbol_exist["symbol"], shares, current_price, purchases_date[0]["datetime()"])
        # Pops up a message to the user
        flash("Bought!")
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Lando was here...
    history = db.execute("SELECT symbol, shares, price, purchases_date FROM purchases WHERE purchases_id = ?", session["user_id"])

    return render_template("history.html", history=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        # werkzeug.security.check_password_hash(pwhash, password) is used for checking a password against a given salted and hashed password value.
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
    # Lando was here
    if request.method == "POST":
        symbol = request.form.get("symbol")

        # Use lookup from helpers.py function to get the quote
        quote = lookup(symbol)

        # Check if the quote doesn't exist
        if quote == None:
            return apology("invalid symbol")
        return render_template("quoted.html", quote=quote)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Lando was here ...
    if request.method == "POST":

        # Check username
        username = request.form.get("username")
        db_username = db.execute("SELECT username FROM users WHERE username = ?", username)
        if not username:
            return apology("must provide username")
        elif len(db_username) != 0:
            return apology("username is already taken")

        # Check password
        password = request.form.get("password")
        password_confirm = request.form.get("confirmation")
        if not password or not password_confirm:
            return apology("must provide password")
        elif password != password_confirm:
            return apology("passwords do not match")

        # Hash Password
        password_hashed = generate_password_hash(password)
        # Store username and password inside database
        db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", username, password_hashed)
        flash("Registered!")
        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Lando was here ...
    # Get stocks that the user's owned
    stocks = db.execute("SELECT owned_symbol FROM owned WHERE owned_id = ?", session["user_id"])

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Check if user's not selecting any stocks and shares
        if not symbol:
            return apology("missing symbol")
        elif not shares or not shares.isdigit():
            return apology("invalid shares")

        # Get user stocks from database and convert share to integer
        owned_db = db.execute("SELECT owned_symbol, owned_shares FROM owned WHERE owned_symbol = ? AND owned_id = ?",
                              symbol.upper(), session["user_id"])
        shares = int(request.form.get("shares"))

        # Check if user's doesn't have that stock
        if symbol not in owned_db[0]["owned_symbol"]:
            return apology("symbol not owned")
        # Check if the shares is negative number or more than what the user has.
        elif shares < 0 or shares > owned_db[0]["owned_shares"]:
            return apology("invalid shares")

        # Delete the user's shares if the user sell all of their shares, otherwise subtract the user's shares
        if shares == owned_db[0]["owned_shares"]:
            db.execute("DELETE FROM owned WHERE owned_symbol = ? AND owned_id = ?", symbol.upper(), session["user_id"])
        else:
            db.execute("UPDATE owned SET owned_shares = ? WHERE owned_symbol = ? AND owned_id = ?",
                       owned_db[0]["owned_shares"] - shares, symbol.upper(), session["user_id"])

        # Add the user's cash
        users_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        current_price = lookup(symbol)["price"]
        sell_price = current_price * shares
        db.execute("UPDATE users SET cash = ? WHERE id = ?", users_cash[0]["cash"] + sell_price, session["user_id"])

        # Insert to other database to keep track of the user sell history
        sell_date = db.execute("SELECT datetime()")
        db.execute("INSERT INTO purchases(purchases_id, symbol, shares, price, purchases_date) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], symbol.upper(), -shares, current_price, sell_date[0]["datetime()"])
        flash("Sold!")
        return redirect("/")

    return render_template("sell.html", stocks=stocks)


# Add my own features


@app.route("/topup", methods=["GET", "POST"])
@login_required
def topup():
    """ Top-up more cash """
    # Lando was here...
    max_topup = 10000
    if request.method == "POST":
        topup = request.form.get("topup")

        # Check if the user doesn't specify the amount or not digit
        if not topup or not topup.isdigit():
            return apology("invalid top-up")

        #  Cast to float and check if top up less than 0, more than 10000
        topup = float(topup)
        if topup < 0 or topup > max_topup:
            return apology("invalid top-up")

        # Update the user cash
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", current_cash[0]["cash"] + topup, session["user_id"])
        # Pops up a message
        flash("Succeed!")
        return redirect("/")

    return render_template("topup.html", max_topup=max_topup)


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """ Change the user password """
    # Lando was here...
    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        # Check passwords
        if not password or not confirm_password:
            return apology("must provide password", 403)
        elif password != confirm_password:
            return apology("passwords do not match", 403)

        password_hashed = generate_password_hash(password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", password_hashed, session["user_id"])
        flash("Password Changed!")
        return redirect("/")

    return render_template("password.html")
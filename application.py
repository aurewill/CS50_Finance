import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    if request.method == "GET":

        # Get list of stocks
        stocksList = []
        stocks = db.execute("SELECT DISTINCT stock FROM purchases WHERE buyer_id = ?", session["user_id"])
        for DICT in stocks:
            stocksList.append(DICT["stock"])

        # Get list of shares
        sharesList = []
        for stock in stocksList:
            shares = db.execute("SELECT SUM(shares) FROM purchases WHERE buyer_id = ? AND stock = ?", session["user_id"], stock)
            sharesList.append(shares[0]["SUM(shares)"])

        # Get list of current prices
        pricesList = []
        for stock in stocksList:
            DICT = lookup(stock)
            price = DICT["price"]
            pricesList.append(price)

        # Get list of total values (shares*price)
        totalValList = []
        for i in range(len(sharesList)):
            totalVal = round(sharesList[i] * pricesList[i], 2)
            totalValList.append(totalVal)

        # Get cash balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cashBal = cash[0]["cash"]

        # Get grand total
        TOTALVAL = 0
        for val in totalValList:
            TOTALVAL += val
        grandTotal = round(cashBal + TOTALVAL, 2)

        # Put into from of USD
        LENGTH = len(stocksList)

        for j in range(LENGTH):
            pricesList[j] = usd(pricesList[j])

        for k in range(LENGTH):
            totalValList[k] = usd(totalValList[k])

        cashBal = usd(cashBal)

        grandTotal = usd(grandTotal)

        LENGTH = len(stocksList)

        return render_template("index.html", stocksList=stocksList, sharesList=sharesList, pricesList=pricesList, totalValList=totalValList, cashBal=cashBal, grandTotal=grandTotal, LENGTH=LENGTH)

    else:

        # Ensure user inputted some text
        if not request.form.get("addCash"):
            return apology("must provide amount", 403)

        # Ensure number of shares is a positive int
        elif int(request.form.get("addCash")) <= 0:
            return apology("invalid amount", 403)

        # Add cash
        else:

            addCash = float(request.form.get("addCash"))

            cashList = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash = float(cashList[0]["cash"])

            setCash = round(addCash + cash, 2)

            db.execute("UPDATE users SET cash = ? WHERE id = ?", setCash, session["user_id"])

            return redirect("/")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")

    else:

        # Ensure user inputted some text
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 403)

        # Ensure stock symbol is valid
        elif lookup(request.form.get("symbol")) == None:
            return apology("invalid stock symbol", 403)

        # Ensure user inputted some text
        elif not request.form.get("shares"):
            return apology("must provide # of shares", 403)

        # Ensure number of shares is a positive int
        elif int(request.form.get("shares")) <= 0:
            return apology("invalid amount", 403)

        # Buy stock
        else:

            quoteDict = lookup(request.form.get("symbol"))
            name = quoteDict["symbol"]
            price = round(quoteDict["price"], 2)
            amount = int(request.form.get("shares"))
            row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash = row[0]["cash"]

            # Not enough cash
            if (price*amount) > cash:
                return apology("not enough cash", 403)

            # Complete purchase
            else:
                newCash = round(cash - (price*amount), 2)
                db.execute("INSERT INTO purchases (buyer_id, stock, price, shares, total, time) VALUES (?,?,?,?,?,?)", \
                            session["user_id"], name, price, amount, round(price*amount, 2), datetime.now())

                db.execute("UPDATE users SET cash = ? WHERE id = ?", newCash, session["user_id"])

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    BIG_LIST = db.execute("SELECT stock,price,shares,time FROM purchases WHERE buyer_id = ?", session["user_id"])

    return render_template("history.html", BIG_LIST=BIG_LIST)


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
    if request.method == "GET":
        return render_template("quote.html")

    else:

        # Ensure user inputted some text
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 403)

        # Ensure stock symbol is valid
        elif lookup(request.form.get("symbol")) == None:
            return apology("invalid stock symbol", 403)

        # Find stock price
        else:
            quoteDict = lookup(request.form.get("symbol"))
            price = usd(quoteDict["price"])
            name = quoteDict["name"]
            return render_template("quoted.html", name=name, price=price)


@app.route("/register", methods=["GET", "POST"])
def register():

    """Direct to register.html or INSERT info into finance.db"""
    if request.method == "GET":
        return render_template("register.html")

    else:

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)

        # Ensure password and confirmation match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords don't match", 403)

        # Query database to insert registrant
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "GET":
        return render_template("sell.html")

    else:

        # Ensure user inputted some text
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 403)

        # Ensure stock symbol is valid
        elif lookup(request.form.get("symbol")) == None:
            return apology("invalid stock symbol", 403)

        # Ensure user inputted some text
        elif not request.form.get("shares"):
            return apology("must provide # of shares", 403)

        # Ensure number of shares is a positive int
        elif int(request.form.get("shares")) <= 0:
            return apology("invalid amount", 403)

        # Sell stock
        else:

            # Ensure user has enough shares to sell
            amount = int(request.form.get("shares"))
            stock = request.form.get("symbol")
            shares = db.execute("SELECT SUM(shares) FROM purchases WHERE buyer_id = ? AND stock = ?", session["user_id"], stock)
            sharesOwned = shares[0]["SUM(shares)"]

            if sharesOwned < amount:
                return apology("not enough shares owned", 403)

            else:

                # Complete sale
                quoteDict = lookup(request.form.get("symbol"))
                name = quoteDict["symbol"]
                price = round(quoteDict["price"], 2)
                row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                cash = row[0]["cash"]

                newCash = round(cash + (price*amount), 2)
                db.execute("INSERT INTO purchases (buyer_id, stock, price, shares, total, time) VALUES (?,?,?,?,?,?)", \
                            session["user_id"], name, price, amount*-1, round(price*amount*-1, 2), datetime.now())

                db.execute("UPDATE users SET cash = ? WHERE id = ?", newCash, session["user_id"])

        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

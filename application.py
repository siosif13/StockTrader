import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

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


@app.route("/")
@login_required
def index():

    items = db.execute("SELECT * FROM portfolio WHERE user_id = :id", id = session["user_id"])
    totalBalance = 0
    for item in items: 
        tmp = lookup(item["symbol"])
        totalBalance += tmp["price"] * item["shares"]
        item["price"] = usd(tmp["price"])
        item["total"] = usd(item["total"])

    q = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])


    return render_template("index.html", name = session["user_name"], cash = usd(q[0]["cash"]), 
        totalBalance = usd(totalBalance + q[0]["cash"]) , items = items)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        stock = lookup(request.form.get("symbolBuy"))
        if not stock:
            return apology("Stock inexistent", 403)
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        userMoney = rows[0]["cash"]
        if float(stock["price"]) * int(request.form.get("stockNb")) > userMoney:
            return apology("cash exceeded", 403)
        else: 
            total_price = float(stock["price"]) * int(request.form.get("stockNb"))

            q = db.execute("SELECT * FROM portfolio WHERE symbol = :symbol AND user_id = :id", 
                symbol = request.form.get("symbolBuy"), id = session["user_id"])
            if len(q) != 1: 
                q = db.execute("INSERT INTO portfolio (user_id, stock, symbol, shares, price_per_stock, total) VALUES (:uid, :stock, :symbol, :shares, :price, :total)", 
                    uid = session["user_id"], stock = stock["name"], symbol = stock["symbol"],
                    shares = int(request.form.get("stockNb")), price = stock["price"], total = total_price)
            else:
                q = db.execute("UPDATE portfolio SET shares = shares + :shares, total = total + :shares * price_per_stock WHERE symbol = :symbol AND user_id = :id", 
                    shares = int(request.form.get("stockNb")), symbol = stock["symbol"], id = session["user_id"])


            q = db.execute("INSERT INTO history (user_id, buy_sell, symbol, price, shares, date_time) VALUES (:uid, :buy, :symb, :price, :shares, :dt)", 
                uid = session["user_id"], buy = "Buy", symb = request.form.get("symbolBuy"), price = stock["price"], shares = request.form.get("stockNb"), 
                dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))           

            q = db.execute("UPDATE users SET cash = :final WHERE id = :uid", final = userMoney - total_price, uid = session["user_id"])
            return redirect(url_for("index"))
    return render_template("buy.html")

@app.route("/history")
@login_required
def history():
        

    q = db.execute("SELECT * FROM history WHERE user_id = :uid", uid = session["user_id"])

    return render_template("history.html", items = q)

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
        session["user_name"] = rows[0]["username"]

        # Redirect user to home page
        return redirect(url_for("index"))

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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a symbol")
        else:
            quote = lookup(symbol)
            if not quote:
                return render_template("quote.html")
            else:
                return render_template("quoted.html", name = quote["name"], price = usd(quote["price"]),
                    symbol = quote["symbol"])
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("Must provide username", 403)
        if not request.form.get("password"):
            return apology("Must provide a valid password", 403)
        if not request.form.get("rePassword"):
            return apology("Incorrect retyped password", 403)
        if request.form.get("password") != request.form.get("rePassword"):
            return apology("Passwords do not match", 403)
        else:
            rows = db.execute("INSERT INTO users (username, hash) VALUES (:usr, :pas)", 
                usr=request.form.get("username"), pas=generate_password_hash(request.form.get("password")))
            session["user_id"] = rows
            session["user_name"] = request.form.get("username")
            if not rows:
                return apology("Acest cont exista", 403)
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Must provide a symbol", 403)
        if not request.form.get("shares"):
            return apology("Must provide a number of shares", 403)

        q = db.execute("SELECT shares FROM portfolio WHERE symbol = :symbol AND user_id = :id",
            symbol = request.form.get("symbol"), id = session["user_id"])
        if len(q) != 1:
            return apology("Stock inexistent", 403)
        elif q[0]["shares"] < int(request.form.get("shares")):
            return apology("You don't have enough shares", 403)
        elif q[0]["shares"] == int(request.form.get("shares")):
            q = db.execute("DELETE FROM portfolio WHERE symbol = :symbol and user_id = :id", 
                symbol = request.form.get("symbol"), id = session["user_id"])
        else:
            q = db.execute("UPDATE portfolio SET shares = shares - :shares WHERE user_id = :id AND symbol = :symbol", 
                shares = request.form.get("shares"), id = session["user_id"], symbol = request.form.get("symbol"))

        moneyToAdd = lookup(request.form.get("symbol"))

        q = db.execute("INSERT INTO history (user_id, buy_sell, symbol, price, shares, date_time) VALUES (:uid, :sell, :symb, :price, :shares, :dt)", 
            uid = session["user_id"], sell = "Sell", symb = request.form.get("symbol"), price = moneyToAdd["price"], shares = request.form.get("shares"), 
            dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

        moneyToAdd = float(moneyToAdd["price"]) * int(request.form.get("shares"))
        q = db.execute("UPDATE users SET cash = cash + :cash WHERE id = :id", cash = moneyToAdd, id = session["user_id"])



    cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

    items = db.execute("SELECT * FROM portfolio WHERE user_id = :id", id = session["user_id"])
    for item in items:
        tmp = lookup(item["symbol"])
        item["inPrice"] = usd(item["price_per_stock"])
        item["curPrice"] = usd(tmp["price"])

    return render_template("sell.html", cash = usd(cash[0]["cash"]), items = items)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

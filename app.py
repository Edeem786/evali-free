from flask import Flask, render_template, session, request, redirect, flash
from flask_session import Session
from flask_apscheduler import APScheduler
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import validators
import datetime
import pytz
import time
from functions import login_required, check_start_date, check_achievements


app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SCHEDULER_API_ENABLED'] = True
app.config['SCHEDULER_TIMEZONE'] = 'Asia/Jakarta'
Session(app)

#sqlite3
db = sqlite3.connect("evalifree.db", check_same_thread=False)
cur = db.cursor()

# Every Midnight add everyones streak by 1 every midnight

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

def streak_counter():
    now = datetime.datetime.now()
    print(f"Running daily task at: {now}")
    cur.execute("UPDATE vapecheckin SET checkedin = 0")
    cur.execute("UPDATE userdata SET exptoday = 0")
    db.commit()
# This function will run every day at 00:00 (midnight)
scheduler.add_job(id="streak_counter", func=streak_counter, trigger='cron', hour=0, minute=0)


@app.route("/")
def home():
    if "user_id" in session:
        user_id = session["user_id"]
        check_achievements()
        userdata = cur.execute("SELECT streakstart FROM userdata WHERE user_id = ?", [session["user_id"]]).fetchone()
        if userdata[0]:
        # check if the current time has passed the time to start quitting
            if check_start_date():
                cur.execute("UPDATE userdata SET started = 1 WHERE user_id = ?", [user_id])
                db.commit()
        # check whether or not user has checked in for the day    
            checkedin = cur.execute("SELECT checkedin FROM vapecheckin WHERE user_id = ?", [user_id]).fetchone()
            check2 = cur.execute("SELECT started FROM userdata WHERE user_id = ?", [user_id]).fetchone()
            if (not checkedin or checkedin[0] != 1)and check2[0] != 0: # checkedin == 0 means the user has not entered checked in
                return redirect("/checkin")

        logindata = cur.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)).fetchone()
        userdata = cur.execute("SELECT * FROM userdata WHERE user_id = ?", (user_id,)).fetchone()
    else:
        logindata = None
        userdata = None
    return render_template("home.html", logindata=logindata, userdata=userdata)

@app.route("/register", methods=["GET","POST"])
def register():
    if "user_id" in session:
        session.clear()

    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username").strip().title()
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        city = request.form.get("city").strip().title()
        state = request.form.get("state").strip().title()
        country = request.form.get("country").strip().title()
        time = datetime.datetime.now(pytz.timezone("Asia/Jakarta"))
        # making sure input is not empty
        if not username or not password or not confirmation:
            flash("Missing Input")
            return redirect("/register")

        # making sure passwords match
        if password != confirmation:
            flash("Passwords do not match")
            return redirect("/register")

        # make sure the email is a valid email
        if not validators.email(email):
            flash("Email is not valid")
            return redirect("/register")

        # check if username is already taken (not case sensitive)
        rows = cur.execute("SELECT * FROM users WHERE username = ?", [username]).fetchone()
        if rows != None:
            flash("Username is taken")
            return redirect("/register")

        # hash password
        hash = generate_password_hash(password)

        # insert into databases

        cur.execute("INSERT INTO users (username, hash, email, city, state, country) VALUES (?, ?, ?, ?, ?, ?)", (username, hash, email, city, state, country))

        rows = cur.execute("SELECT * FROM users WHERE username LIKE ?", [username]).fetchone()

        # log the user to registered account
        session["user_id"] = rows[0]

        cur.execute("INSERT INTO userdata (user_id, time_created, streak, exp) VALUES (?, ?, ?, ?)", (session["user_id"], time, 0, 0))
        cur.execute("INSERT INTO vapecheckin (user_id)  VALUES (?)", [session["user_id"]])
        db.commit()

        flash("Succesfully Registered Account!")
        return redirect("/")

@app.route("/login", methods=["GET","POST"])
def login():
    # Forget any user_id
    if "user_id" in session:
        session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Missing username")
            return redirect("/login")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return redirect("/login")

        # Query database for username
        rows = cur.execute("SELECT * FROM users WHERE username = ?", [request.form.get("username")]).fetchone()
        
        # Ensure username exists and password is correct    
        if not rows:
            rows = cur.execute("SELECT * FROM users WHERE email = ?", [request.form.get("username")]).fetchone()
            if not rows:
                flash("Invalid username or email")
                return redirect("/login")
            
        if not check_password_hash(rows[2], request.form.get("password")):
            flash("Invalid password")
            return redirect("/login")
        
        session["user_id"] = rows[0]

        flash("Successfully logged in!")
        return redirect("/")

    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()

    # Redirect user
    flash("Successfully logged out")
    return redirect("/")

@app.route("/about")
def about():
    return render_template("aboutus.html")

@app.route("/start", methods=["GET","POST"])
@login_required
def start():
    if request.method == "GET":
        return render_template("start.html")
    else:
        reason = request.form.get("reasons")
        date = request.form.get("quitDate")
        moneyPerDay = float(request.form.get("moneyperweek")) / 7
        if not reason:
            flash("Missing Input")
            return redirect("/start")
        if check_start_date():
            start_value = 1 # 1 means the user has started quitting
        else:
            start_value = 0
        cur.execute("UPDATE userdata SET goals = ?, streakstart = ?, moneyperday = ?, started = ?, totalnovape = ? WHERE user_id = ?", (reason, date, moneyPerDay, start_value, 0, session["user_id"]))
        print(date)
        db.commit()

        return redirect("/")
    
@app.route("/leaderboards")
def leaderboard():
    streak_counter()
    topten = cur.execute("SELECT username, exp FROM users LEFT JOIN userdata ON users.user_id = userdata.user_id ORDER BY exp DESC LIMIT 10").fetchall()
    print (topten)
    return render_template("leaderboard.html", topten=topten)

@app.route("/track")
@login_required
def track():
    logindata = cur.execute("SELECT * FROM users WHERE user_id = ?",[session["user_id"]]).fetchone()
    userdata = cur.execute("SELECT * FROM userdata WHERE user_id = ? ",[session["user_id"]]).fetchone()
    return render_template("track.html", logindata=logindata, userdata=userdata)

@app.route("/community", methods=["GET","POST"])
@login_required
def community():
    if request.method == "GET":
        stories = cur.execute("SELECT name, story FROM community ORDER BY RANDOM() LIMIT 30").fetchall()
        return render_template("community.html", stories=stories)
    else:
        name = request.form.get("name")
        story = request.form.get("story")
        
        # ensure valid input
        if not name or not story:
            flash("missing input")
            return redirect("/community")

        cur.execute("INSERT INTO community (name, story) VALUES (? , ?)", (name, story))
        db.commit()
        flash("Successfully uploaded story!")
        return redirect("/community")

@app.route("/checkin", methods=["GET","POST"])
@login_required
def check_in():
    if request.method == "GET":
        # make sure user has not actually checked in for the day
        checkedin = cur.execute("SELECT checkedin FROM vapecheckin WHERE user_id = ?", [session["user_id"]]).fetchone()
        started = cur.execute("SELECT started FROM userdata WHERE user_id = ?", [session["user_id"]]).fetchone()[0]
        if (checkedin and checkedin[0] == 1) or started == 0: # checkin == 0 means the user has not entered checked in
            return redirect("/")

        return render_template("checkin.html")
    else:
        answer = request.form.get("answer")
        startdate = cur.execute("SELECT streakstart FROM userdata WHERE user_id = ?", [session["user_id"]]).fetchone()
        
        if not answer:
            flash("Invalid answer")
            return redirect("/checkin")
        else:
            answer = datetime.datetime.strptime(startdate[0], "%Y-%m-%d").date()
        if not startdate:
            flash("Invalid Starting Date")
            startdate = datetime.datetime.now(pytz.timezone("Asia/Jakarta"))
        else:
            start = datetime.datetime.strptime(startdate[0], "%Y-%m-%d").date()
        if start > answer:
            cur.execute("UPDATE userdata SET streak = streak + 1, exp = exp + 10 + streak, exptoday = exptoday + 10 + streak, totalnovape = totalnovape + 1 WHERE user_id = ?", [session["user_id"]])
        else:
            flash("better luck next time..")
            cur.execute("UPDATE userdata SET streakstart = ?, streak = 0 WHERE user_id = ?", (datetime.datetime.now(pytz.timezone("Asia/Jakarta")), session["user_id"]))

        # update the database to indicate that user has logged in
        cur.execute("UPDATE vapecheckin SET checkedin = 1 WHERE user_id = ?", [session["user_id"]])
        db.commit()
        return redirect("/")

@app.route("/achievements")
@login_required
def achievements():
    badges_str = cur.execute("SELECT badges FROM userdata WHERE user_id = ?", [session["user_id"]]).fetchone()
    if badges_str:
        try:
            badges = badges_str[0].split(",")
        except:
            badges = []
    allbadges = [
        "Vape-free-day",
        "Vape-free-week",
        "Vape-free-month",
        "Vape-free-year",
    ]
    unearned = []
    for badge in allbadges:
        if badge not in badges:
            unearned.append(badge)
    return render_template("achievements.html", badges=badges, unearned=unearned)

if __name__ == "__main__":
    app.run(debug=True)
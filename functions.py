from flask import redirect, session
from functools import wraps
import datetime
import pytz
import sqlite3

db = sqlite3.connect("evalifree.db", check_same_thread=False)
cur = db.cursor()

def login_required(f):
    # Decorate routes to require login.
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def check_start_date():
    startdate = cur.execute("SELECT streakstart FROM userdata WHERE user_id = ?", [session["user_id"]]).fetchone()
    if not startdate[0]:
        return None
    start = datetime.datetime.strptime(startdate[0], "%Y-%m-%d").date()
    #print(datetime.datetime.now(pytz.timezone("Asia/Jakarta")).date())
    if datetime.datetime.now(pytz.timezone("Asia/Jakarta")).date() > start:
        return True
    else:
        return False
    
def check_achievements():
    userdata = cur.execute("SELECT streak, badges FROM userdata WHERE user_id = ?", [session["user_id"]]).fetchone()
    if not userdata:
        return None
    
    streak = int(userdata[0])
    if not userdata[1]:
        badge = ""
    else:
        badge = userdata[1]
    expgained = 0
    if streak >= 1 and "Vape-free-day" not in badge:
        badge = badge + "Vape-free-day,"
        expgained += 30
    if streak >= 7 and "Vape-free-week" not in badge:
        badge = badge + "Vape-free-week,"
        expgained += 300
    if streak >= 30 and "Vape-free-month" not in badge:
        badge = badge + "Vape-free-month,"
        expgained += 2000
    if streak >= 365 and "Vape-free-year" not in badge:
        badge = badge + "Vape-free-year,"
        expgained += 50000
    
    cur.execute("UPDATE userdata SET exp = exp + ?, exptoday = exptoday + ?, badges = ? WHERE user_id = ?", (expgained, expgained, badge, session["user_id"]))
    db.commit()
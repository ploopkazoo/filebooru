#! /usr/bin/env python3

import base64
import datetime
import hashlib
import os

import psycopg2
from flask import Flask, request, render_template, make_response, redirect
from filebooru_settings import fb_confd, fb_conn, fb_common, fb_strings

conn = psycopg2.connect(
    dbname=fb_conn["database"],
    user=fb_conn["username"],
    host=fb_conn["hostname"],
    password=fb_conn["password"]
)
app = Flask(__name__)

sessions = {}

def human_size(bytecount):
    itters = 0
    while bytecount >= 1024:
        itters += 1
        bytecount /= 1024
    if itters == 0:
        return "%i %s" % (bytecount, "B")
    else:
        return "%.2f %s" % (bytecount, ["B", "KiB", "MiB", "GiB", "TiB", "PiB"][itters])

def getusername(cookies):
    session = cookies.get("session")
    try:
        username = sessions[session]
    except:
        username = None
    return username

@app.route("/")
def render_root():
    username = getusername(request.cookies)
    return render_template("list.html", com=fb_common,
        username=(username if username else "Login"))

@app.route("/signin")
def render_signin():
    return render_template("signin.html", com=fb_common)

@app.route("/signup")
def render_signup():
    return render_template("signup.html", com=fb_common)

@app.route("/user/me")
def render_me():
    username = getusername(request.cookies)
    if username:
        return redirect("/user/by-username/%s" % username)
    else:
        return redirect("/signin")

@app.route("/user/<int:userid>")
def render_user(userid):
    cur = conn.cursor()
    cur.execute("SELECT userid, username, registered FROM users WHERE userid = %s", (userid,))
    response = cur.fetchone()
    return "%s (%i)<br />Registered %s" % (response[1], response[0],
        datetime.datetime.strftime(response[2], "%Y-%m-%d %H:%M:%S"))

@app.route("/user/by-username/<username>")
def render_user_by_username(username):
    cur = conn.cursor()
    cur.execute("SELECT userid FROM users WHERE username = %s", (username,))
    response = cur.fetchone()
    return redirect("/user/%i" % response)

@app.route("/file/<fileid>")
def render_file(fileid):
    return render_template("file.html")

@app.route("/mock/<page>")
def render_mock(page):
    return render_template(page + ".html", com=fb_common)

@app.route("/register", methods=["POST"])
def register():
    username, password = request.form["username"], request.form["password"]
    newsalt = base64.b64encode(os.urandom(21)).decode("utf-8")
    newhash = hashlib.sha256(newsalt.encode("utf-8") + password.encode("utf-8")).hexdigest()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, admin, salt, hash, registered, groups) VALUES \
    (%s, %s, %s, %s, %s, %s)", (username, False, newsalt, newhash, datetime.datetime.now(), [1]))
        return redirect("/")
    except psycopg2.IntegrityError:
        return render_template("error.html", message=fb_strings["username_exists"],
            return_to="/signup", com=fb_common)
    finally:
        conn.commit()

@app.route("/auth", methods=["POST"])
def auth():
    username, password = request.form["username"], request.form["password"]
    cur = conn.cursor()
    cur.execute("SELECT salt, hash FROM users WHERE username = %s", (username,))
    usersalt, userhash = cur.fetchone()
    tryhash = hashlib.sha256(usersalt.encode("utf-8") + password.encode("utf-8")).hexdigest()
    if tryhash == userhash:
        newsession = base64.b64encode(os.urandom(21)).decode("utf-8")
        sessions[newsession] = username
        reply = make_response(redirect("/"))
        reply.set_cookie("session", newsession)
        return reply
    else:
        return render_template("error.html", message=fb_strings["incorrect_login"])

@app.route("/qqq")
def qqq():
    print("------------")
    for meme in sessions.keys():
        print("%s   %s" % (meme, sessions[meme]))
    print("------------")
    return ""

if __name__ == "__main__":
    app.run(debug=True)

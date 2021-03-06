#! /usr/bin/env python3

import base64
import datetime
import hashlib
import os

import psycopg2
import magic
from flask import Flask, Markup, request, render_template, make_response, redirect, Response
from werkzeug import secure_filename
from filebooru_settings import fb_confd, fb_filedir, fb_conn, fb_common, fb_strings, fb_options

conn = psycopg2.connect(
    dbname=fb_conn["database"],
    user=fb_conn["username"],
    host=fb_conn["hostname"],
    password=fb_conn["password"]
)
app = Flask(__name__)

sessions = {}

@app.template_filter("human_size")
def human_size(bytecount):
    itters = 0
    while bytecount >= 1024:
        itters += 1
        bytecount /= 1024
    if itters == 0:
        return "%i %s" % (bytecount, "B")
    else:
        return "%.2f %s" % (bytecount, ["B", "KiB", "MiB", "GiB", "TiB", "PiB"][itters])

@app.template_filter("comma_list")
def comma_list(inlist):
    return ", ".join(inlist)

@app.template_filter("date_string")
def date_string(date):
    return datetime.datetime.strftime(date, "%Y-%m-%d")

@app.template_filter("datetime_string")
def datetime_string(date):
    return datetime.datetime.strftime(date, "%Y-%m-%d %H:%M:%S")

@app.template_filter("fixnewlines")
def fixnewlines(in_text):
    return Markup(str(Markup.escape(in_text)).replace("\n", "<br/>"))

def getusername(cookies):
    session = cookies.get("session")
    try:
        username = sessions[session]
    except:
        username = None
    return username

def name2id(username):
    cur = conn.cursor()
    cur.execute("SELECT userid FROM users WHERE username = %s", (username,))
    return cur.fetchone()

def readfile(fileid):
    cur = conn.cursor()
    cur.execute("SELECT sha256, filename, mime FROM files WHERE fileid = %s", (fileid,))
    filehash, filename, mime = cur.fetchone()
    sourcepath = os.path.realpath(os.path.join(fb_filedir, filehash))
    return open(sourcepath, "rb").read(), mime, filename

def allowed_to_read(userid, fileid):
    if fb_options["all_files_public"]:
        return True
    cur = conn.cursor()
    cur.execute("SELECT public FROM files WHERE fileid = %s", (fileid))
    if cur.fetchone()[0]:
        return True
    cur.execute("SELECT ((SELECT groups::int[] FROM users WHERE userid = %s) \
        && (SELECT readgroups::int[] FROM files WHERE fileid = %s) OR \
        (SELECT count(*) = 1 FROM files WHERE owner = %s AND fileid = %s))", \
        (userid, fileid, userid, fileid))
    authorized = bool(cur.fetchone()[0])
    return authorized

@app.route("/")
def render_root():
    username = getusername(request.cookies)
    cur = conn.cursor()
    cur.execute("SELECT files.fileid, files.extension, files.filename, files.tags, \
        users.username FROM files INNER JOIN users ON users.userid = files.owner \
        ORDER BY uploaded DESC LIMIT 25")
    response = cur.fetchall()
    return render_template("list.html", data=response, com=fb_common,
        username=(username if username else "Login"))

@app.route("/signin")
def render_signin():
    return render_template("signin.html", com=fb_common,
        allow_signups=fb_options["allow_account_creation"])

@app.route("/signup")
def render_signup():
    if not fb_options["allow_account_creation"]:
        return render_template("error.html", message=fb_strings["reg_disabled"],
            return_to="/", com=fb_common, username=(username if username else "Login"))
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
    username = getusername(request.cookies)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE userid = %s", (userid,))
    response = cur.fetchone()
    return render_template("user.html", com=fb_common, data=response,
        username=(username if username else "Login"))

@app.route("/user/by-username/<username>")
def render_user_by_username(username):
    cur = conn.cursor()
    cur.execute("SELECT userid FROM users WHERE username = %s", (username,))
    response = cur.fetchone()
    return redirect("/user/%i" % response)

@app.route("/file/<fileid>/")
def render_file(fileid):
    username = getusername(request.cookies)
    userid = name2id(username)
    cur = conn.cursor()
    if not allowed_to_read(userid, fileid):
        return render_template("error.html", com=fb_common, message=fb_strings["read_denied"],
            return_to="/", username=(username if username else "Login"))
    cur.execute("SELECT files.filename, files.bytes, users.username, files.uploaded, \
        files.tags, files.sha256, files.description FROM files INNER JOIN users ON files.owner = \
        users.userid WHERE files.fileid = %s", (fileid,))
    response = cur.fetchone()
    return render_template("file.html", com=fb_common, data=response, fileid=fileid,
        filename=response[0], username=(username if username else "Login"))

@app.route("/open/<fileid>/<fname>")
def file_open(fileid, fname):
    username = getusername(request.cookies)
    data, mime, filename = readfile(fileid)
    return Response(data, mimetype=mime,
        headers={"Content-Disposition":"inline"})

@app.route("/download/<fileid>/<fname>")
def file_download(fileid, fname):
    username = getusername(request.cookies)
    data, mime, filename = readfile(fileid)
    return Response(data, mimetype=mime,
        headers={"Content-Disposition":"attachment"})

@app.route("/upload")
def render_upload():
    username = getusername(request.cookies)
    if username == None:
        return render_template("error.html", com=fb_common, message=fb_strings["need_login"],
            username=(username if username else "Login"), return_to="/")
    cur = conn.cursor()
    cur.execute("SELECT groupname, groupid FROM groups INNER JOIN \
        (SELECT unnest(groups) FROM users WHERE userid = %s) unnested \
        ON groups.groupid = unnested.unnest;", (name2id(username),))
    groups = cur.fetchall()
    return render_template("upload.html", com=fb_common, groups=groups,
        username=(username if username else "Login"))

@app.route("/search", methods=["POST"])
def search():
    username = getusername(request.cookies)
    cur = conn.cursor()
    prequery = request.form["query"].lower()
    while "  " in prequery:
        prequery = prequery.replace("  ", " ")
    query = prequery.split(" ")
    mandatory = []
    negated = []
    for tag in query:
        if tag.startswith("-"):
            negated.append(tag[1:])
        else:
            mandatory.append(tag)
    if mandatory and negated and (set(mandatory) & set(negated) != set()):
        response = []
    else:
        cur.execute("SELECT files.fileid, files.extension, files.filename, files.tags, \
        users.username FROM files INNER JOIN users ON users.userid = files.owner WHERE \
        ((tags @> %s AND NOT tags && %s) OR filename ILIKE '%%' || %s || '%%') ORDER BY \
        uploaded DESC", (mandatory, negated, " ".join(query)))
        response = cur.fetchall()
        print(response)
    return render_template("list.html", data=response, com=fb_common,
        username=(username if username else "Login"))

@app.route("/register", methods=["POST"])
def register():
    if not fb_options["allow_account_creation"]:
        return render_template("error.html", message=fb_strings["reg_disabled"],
            return_to="/", com=fb_common, username="Login")
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
    try:
        usersalt, userhash = cur.fetchone()
    except TypeError:
        return render_template("error.html", message=fb_strings["incorrect_login"],
            return_to="/signin", username="Login", com=fb_common)
    tryhash = hashlib.sha256(usersalt.encode("utf-8") + password.encode("utf-8")).hexdigest()
    if tryhash == userhash:
        newsession = base64.b64encode(os.urandom(21)).decode("utf-8")
        sessions[newsession] = username
        reply = make_response(redirect("/"))
        reply.set_cookie("session", newsession)
        return reply
    else:
        return render_template("error.html", message=fb_strings["incorrect_login"],
            return_to="/signin", username="Login", com=fb_common)

@app.route("/makefile", methods=["POST"])
def makefile():
    username = getusername(request.cookies)
    userid = name2id(username)
    filetags = request.form["tags"].split(" ")
    description = request.form["description"]
    filename = request.files["file"].filename.replace("/", "_").replace("?", "_")
    extension = (filename.split(".")[-1] if "." in filename else "")
    filedata = request.files["file"].stream.read()
    filehash = hashlib.sha256(filedata).hexdigest()
    mime = magic.Magic(mime=True).from_buffer(filedata).decode("utf-8")
    destpath = os.path.realpath(os.path.join(fb_filedir, filehash))
    filelen = len(filedata)
    if not os.path.exists(destpath):
        open(destpath, "wb").write(filedata)
    cur = conn.cursor()
    cur.execute("SELECT groupid FROM groups INNER JOIN \
        (SELECT unnest(groups) FROM users WHERE userid = %s) unnested \
        ON groups.groupid = unnested.unnest;", (name2id(username),))
    groups = [x[0] for x in cur.fetchall()]
    read, write = ([],[])
    if request.form.get("public"):
        public = True
    else:
        public = False
        for g in groups:
            if request.form.get("r" + str(g)):
                read.append(g)
            if request.form.get("w" + str(g)):
                write.append(g)
    cur.execute("INSERT INTO files (filename, mime, extension, bytes, uploader, \
        owner, public, readgroups, writegroups, uploaded, tags, sha256, description) \
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING fileid", (
            filename,
            mime,
            extension,
            filelen,
            userid,
            userid,
            public,
            read,
            write,
            datetime.datetime.now(),
            filetags,
            filehash,
            description
        ))
    newid = cur.fetchone()[0]
    conn.commit()
    return redirect("/file/%i" % newid)

if __name__ == "__main__":
    app.run(debug=fb_options["flask_debug"])

#! /usr/bin/env python3

from flask import Flask, request, render_template
from filebooru_settings import fb_confd, fb_conn, fb_common

app = Flask(__name__)

def human_size(bytecount):
    itters = 0
    while bytecount >= 1024:
        itters += 1
        bytecount /= 1024
    if itters == 0:
        return "%i %s" % (bytecount, "B")
    else:
        return "%.2f %s" % (bytecount, ["B", "KiB", "MiB", "GiB", "TiB", "PiB"][itters])

@app.route("/file/<fileid>")
def render_root(fileid):
    return render_template("file.html")

@app.route("/mock/<page>")
def render_mock(page):
    return render_template(page + ".html", com=fb_common)

if __name__ == "__main__":
    app.run(debug=True)

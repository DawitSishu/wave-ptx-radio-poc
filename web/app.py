"""
WAVE PTX programming dashboard.

A web UI (behind a login) to manage the operational voice prompts and the broadcast
schedule. The scheduler engine reads the same schedule file this app writes, so the
dashboard directly drives what airs on the radios -- no Radio.co needed.

Run:
    pip install -r requirements.txt
    python web/app.py            # http://localhost:8080  (default login: admin / changeme)
"""
import functools
import json
import os

import yaml
from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "audio")
SCHEDULE_FILE = os.path.join(ROOT, "config", "schedule.yaml")
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

app = Flask(__name__)
app.secret_key = os.environ.get("DASHBOARD_SECRET", "dev-secret-change-me")


# --- auth ---
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    users = {"admin": generate_password_hash("changeme")}   # first-run default
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)
    return users


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# --- schedule + media ---
def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {"timezone": "America/Chicago", "broadcasts": []}


def save_schedule(data):
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def list_prompts():
    if not os.path.isdir(AUDIO_DIR):
        return []
    return sorted(f for f in os.listdir(AUDIO_DIR)
                  if f.lower().endswith((".mp3", ".wav")))


# --- routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        users = load_users()
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u in users and check_password_hash(users[u], p):
            session["user"] = u
            return redirect(url_for("dashboard"))
        flash("Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    sched = load_schedule()
    return render_template("dashboard.html", user=session["user"],
                           schedule=sched, prompts=list_prompts(), days=DAYS)


@app.route("/broadcast", methods=["POST"])
@login_required
def add_broadcast():
    sched = load_schedule()
    picked = request.form.getlist("days")
    days = "all" if (not picked or "all" in picked) else picked
    sched.setdefault("broadcasts", []).append({
        "time": request.form["time"],
        "days": days,
        "audio": request.form["audio"],
        "talkgroup": request.form.get("talkgroup", "all-restaurants"),
        "label": request.form.get("label") or request.form["audio"],
    })
    save_schedule(sched)
    flash("Reminder scheduled")
    return redirect(url_for("dashboard"))


@app.route("/broadcast/delete/<int:idx>", methods=["POST"])
@login_required
def delete_broadcast(idx):
    sched = load_schedule()
    items = sched.get("broadcasts", [])
    if 0 <= idx < len(items):
        items.pop(idx)
        save_schedule(sched)
        flash("Reminder removed")
    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    f = request.files.get("file")
    if f and f.filename:
        os.makedirs(AUDIO_DIR, exist_ok=True)
        f.save(os.path.join(AUDIO_DIR, secure_filename(f.filename)))
        flash("Prompt uploaded: %s" % f.filename)
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

"""iOS-optimized Flask server for Werblers board game.

Shares the game engine and all API routes with the desktop web_ui app,
but serves a mobile-optimized HTML/CSS/JS frontend for iOS Safari.

Run:  python ios_ui/app.py   →   http://0.0.0.0:5001
"""
from __future__ import annotations
import os, sys

_IOS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_IOS_DIR)
sys.path.insert(0, _ROOT_DIR)

from flask import Flask, render_template, send_from_directory
import web_ui.app as _desktop  # noqa: E402 – imports desktop app to borrow API routes

app = Flask(
    __name__,
    static_folder=os.path.join(_IOS_DIR, "static"),
    template_folder=os.path.join(_IOS_DIR, "templates"),
)

IMAGES_DIR = os.path.join(_ROOT_DIR, "Images")
MUSIC_DIR  = os.path.join(_ROOT_DIR, "Music")
VIDEOS_DIR = os.path.join(_ROOT_DIR, "Videos")


# ── iOS template ───────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("ios_index.html")


# ── Media routes (shared asset directories) ────────────────────
@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


@app.route("/music/<path:filename>")
def serve_music(filename):
    return send_from_directory(MUSIC_DIR, filename)


@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEOS_DIR, filename)


# ── Import every /api/* route from the desktop app ─────────────
for _rule in _desktop.app.url_map.iter_rules():
    if _rule.rule.startswith("/api/"):
        _ep = _rule.endpoint
        _vf = _desktop.app.view_functions[_ep]
        _methods = list(_rule.methods - {"OPTIONS", "HEAD"})
        app.add_url_rule(_rule.rule, endpoint=_ep, view_func=_vf, methods=_methods)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

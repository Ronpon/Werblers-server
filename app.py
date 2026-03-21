"""Unified Flask server — serves desktop or mobile UI based on User-Agent.

Device detection:
  - Mobile (phones/tablets) → ios_ui/templates/ios_index.html
  - Desktop                 → web_ui/templates/index.html

All /api/* game routes and media routes come from web_ui/app.py.
Static files are served from web_ui/static/ with ios_ui/static/ as fallback.

Run locally:
    python app.py

Deploy on Render (gunicorn):
    gunicorn app:app
"""
from __future__ import annotations
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jinja2 import ChoiceLoader, FileSystemLoader
from flask import request, render_template, send_from_directory

# Import the desktop Flask app — all game state globals and API routes live here.
import web_ui.app as _desktop  # noqa: E402

app = _desktop.app

_ROOT        = os.path.dirname(os.path.abspath(__file__))
_WEB_STATIC  = os.path.join(_ROOT, "web_ui",  "static")
_IOS_STATIC  = os.path.join(_ROOT, "ios_ui",  "static")
_WEB_TMPL    = os.path.join(_ROOT, "web_ui",  "templates")
_IOS_TMPL    = os.path.join(_ROOT, "ios_ui",  "templates")

# ── Multi-folder Jinja2 template loading ───────────────────────────────────
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(_WEB_TMPL),
    FileSystemLoader(_IOS_TMPL),
])

# ── Device detection ───────────────────────────────────────────────────────
_MOBILE_RE = re.compile(
    r"(mobile|android|iphone|ipad|ipod|blackberry|windows\s+phone)",
    re.IGNORECASE,
)

def _is_mobile() -> bool:
    return bool(_MOBILE_RE.search(request.headers.get("User-Agent", "")))

# ── Unified index: desktop vs mobile template ──────────────────────────────
def _unified_index():
    if _is_mobile():
        return render_template("ios_index.html")
    return render_template("index.html")

# Replace the view function that web_ui/app.py registered for '/'
app.view_functions["index"] = _unified_index

# ── Unified static file serving: web_ui/static + ios_ui/static ────────────
def _unified_static(filename: str):
    """Serve from web_ui/static first; fall back to ios_ui/static."""
    if os.path.isfile(os.path.join(_WEB_STATIC, filename)):
        return send_from_directory(_WEB_STATIC, filename)
    return send_from_directory(_IOS_STATIC, filename)

# Replace Flask's built-in static file handler with our merged version
app.view_functions["static"] = _unified_static

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

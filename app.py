"""Project root entry point — delegates to web_ui/app.py.

Run locally:
    python app.py

Deploy on Render (gunicorn):
    gunicorn app:app
"""
import os
import sys

# Ensure project root is on sys.path so 'werblers_engine' is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_ui.app import app  # noqa: E402  (re-exported for gunicorn)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

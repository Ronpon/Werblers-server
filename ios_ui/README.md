# Werblers – iOS / Mobile UI

A touch-optimised display layer for the Werblers board game.  
Runs as a **separate Flask server** (port 5001) alongside the desktop version (port 5000), sharing the same game engine and API routes.

## Quick Start

```bash
# From the project root
pip install flask          # if not already installed
python ios_ui/app.py       # starts on http://0.0.0.0:5001
```

### Opening on iPhone

1. Make sure your iPhone and this PC are on the **same Wi-Fi network**
2. Run the server with `python ios_ui/app.py`
3. On the iPhone open Safari and go to: **http://192.168.0.151:5001**  
   *(This is the Wi-Fi IP printed when the server starts — use the address after* `Running on http://` *that is NOT 127.0.0.1)*
4. Tap the share button → **"Add to Home Screen"** for a full-screen app experience

> **Firewall note (Windows):** Windows Firewall blocks inbound port 5001 by default.
> You must run this **once** in an **Administrator PowerShell** to open it:
>
> ```powershell
> New-NetFirewallRule -DisplayName "Werblers iOS 5001" -Direction Inbound -Protocol TCP -LocalPort 5001 -Action Allow
> ```
>
> *(Or: Start menu → "wf.msc" → Inbound Rules → New Rule → Port → TCP 5001 → Allow → All profiles → name it "Werblers iOS")*

## Architecture

```
ios_ui/
  app.py                   ← Flask wrapper (imports API routes from web_ui)
  README.md                ← This file
  templates/
    ios_index.html          ← Mobile-optimised HTML
  static/
    css/ios_style.css       ← Mobile-first CSS (safe areas, touch targets)
    js/ios_game.js          ← Complete game client adapted for touch
```

- **No existing files are modified.** The desktop `web_ui/` continues to work unchanged on port 5000.
- `ios_ui/app.py` imports all `/api/*` route functions from `web_ui.app` and re-registers them, sharing the same in-memory game state.
- Assets (images, music, videos) are served from the shared project-root directories.

## Key Mobile Adaptations

| Desktop | Mobile |
|---------|--------|
| 3-column layout (board / panel / hero) | Tab-based: Board · Player · Log |
| Hover card previews | Tap-to-zoom |
| Right-click context menus | iOS action sheets |
| Drag-and-drop equip management | Tap-based placement |
| Fixed 78 px tiles | Responsive CSS-grid tiles (10 columns, 1fr) |
| Side-panel modals | Full-screen modal overlays |
| Mouse-follow tooltips | Tap-to-show / auto-dismiss tooltips |

## Requirements

- Python 3.8+
- Flask (`pip install flask`)
- Same `werblers_engine` package used by the desktop app

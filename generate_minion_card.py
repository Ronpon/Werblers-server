"""
Minion Card Generator — composites a portrait onto the Hero Card Template,
adds text overlays for minion name, type, strength, and a centred italic blurb.

Minion cards use the same template as Hero cards, but the bottom text area
contains only the blurb (italic, centred horizontally and vertically).

Usage:
    python generate_minion_card.py                      # generate ALL minions
    python generate_minion_card.py demon_spawn          # generate one by key
    python generate_minion_card.py ted_bearson swamp_friend  # specific minions
"""

from __future__ import annotations

import numpy as np
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


# ═══════════════════════════════════════════════════════════════════════════
# MINION DATA — add new minions here
# ═══════════════════════════════════════════════════════════════════════════

MINIONS: dict[str, dict] = {
    "demon_spawn": {
        "name": "Demon Spawn",
        "type": "Minion",
        "strength": "+7",
        "portrait": "Demon Spawn.png",
        "output": "Demon Spawn Card.png",
        "blurb": "Aww, so\u2026 cute\u2026?",
    },
    "swamp_friend": {
        "name": "Swamp Friend",
        "type": "Minion",
        "strength": "+6",
        "portrait": "Swamp Friend.png",
        "output": "Swamp Friend Card.png",
        "blurb": "Slimy, but very useful.",
    },
    "skeletal_minion": {
        "name": "Skeletal Minion",
        "type": "Minion",
        "strength": "+5",
        "portrait": "Skeletal Minion Portrait.png",
        "output": "Skeletal Minion Card.png",
        "blurb": "Your other minions provide +1 Str.",
    },
    "ex_leper": {
        "name": "Ex-Leper",
        "type": "Minion",
        "strength": "+2",
        "portrait": "Ex-Leper Portrait.png",
        "output": "Ex-Leper Card.png",
        "blurb": "He got better!",
    },
    "weremouse_pal": {
        "name": "Weremouse Pal",
        "type": "Minion",
        "strength": "+8",
        "portrait": "Weremouse Pal Portrait.png",
        "output": "Weremouse Pal Card.png",
        "blurb": "Send him in!",
    },
    "friendly_weredrake": {
        "name": "Friendly Weredrake",
        "type": "Minion",
        "strength": "+3",
        "portrait": "Friendly Weredrake Portrait.png",
        "output": "Friendly Weredrake Card.png",
        "blurb": "It\u2019s oozing.",
    },
    "pet_velociraptor": {
        "name": "Pet Velociraptor",
        "type": "Minion",
        "strength": "+8",
        "portrait": "Pet Velociraptor.png",
        "output": "Pet Velociraptor Card.png",
        "blurb": "Surprisingly clever.",
    },
    "patched_robot": {
        "name": "Patched Robot",
        "type": "Minion",
        "strength": "+3",
        "portrait": "Patched Robot Portrait.png",
        "output": "Patched Robot Card.png",
        "blurb": "Patched the evil right out of it.",
    },
    "ted_bearson": {
        "name": "Ted Bearson",
        "type": "Minion",
        "strength": "+3",
        "portrait": "Ted Bearson.png",
        "output": "Ted Bearson Card.png",
        "blurb": "Gotta grow up sometimes.",
    },
    "apologetic_crumpuff": {
        "name": "Apologetic Crumpuff",
        "type": "Minion",
        "strength": "+3",
        "portrait": "Apologetic Crumpuff Portrait.png",
        "output": "Apologetic Crumpuff Card.png",
        "blurb": "TBD.",
    },
    "spell_catster": {
        "name": "Spell Catster",
        "type": "Minion",
        "strength": "+6",
        "portrait": "Spell Catster Portrait.png",
        "output": "Spell Catster Card.png",
        "blurb": "TBD.",
    },
    "tamed_devil": {
        "name": "Tamed Devil",
        "type": "Minion",
        "strength": "+5",
        "portrait": "Tamed Devil Portrait.png",
        "output": "Tamed Devil Card.png",
        "blurb": "TBD.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS  (matches Hero card template)
# ═══════════════════════════════════════════════════════════════════════════
MINIONS_DIR = Path("Images/Minions")
PORTRAITS_DIR = MINIONS_DIR / "Minion Portraits"
FINISHED_DIR = MINIONS_DIR / "Finished Minion Cards"
TEMPLATE_PATH = MINIONS_DIR / "Minion Card Template.png"

CARD_W, CARD_H = 1024, 1536

# Portrait window (transparent region in template)
PORTRAIT_WINDOW_TOP = 230
PORTRAIT_WINDOW_BOTTOM = 1033
PORTRAIT_WINDOW_LEFT = 48
PORTRAIT_WINDOW_RIGHT = 1008

# Top frame
TYPE_LABEL_POS = (160, 55)
STRENGTH_POS = (910, 62)

# Name banner (parchment, y = 115-230)
NAME_BANNER_TOP = 115
NAME_BANNER_BOTTOM = 230

# Bottom text area (parchment) — blurb centred here
TEXT_AREA_TOP = 1070
TEXT_AREA_LEFT = 142
TEXT_AREA_RIGHT = 882
TEXT_AREA_BOTTOM = 1470
TEXT_LINE_HEIGHT_FACTOR = 1.30


# ═══════════════════════════════════════════════════════════════════════════
# FONTS
# ═══════════════════════════════════════════════════════════════════════════
FONT_DIR = Path(r"C:\Windows\Fonts")


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by filename, falling back to Arial."""
    search_dirs = [FONT_DIR, Path(".")]
    for d in search_dirs:
        for ext in (".ttf", ".otf"):
            p = d / name.replace(".ttf", ext).replace(".otf", ext)
            if p.exists():
                return ImageFont.truetype(str(p), size)
        p = d / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.truetype(str(FONT_DIR / "arial.ttf"), size)


font_type_label = _load_font("Cinzel-Black.ttf", 42)
font_strength = _load_font("Cinzel-Black.ttf", 56)
font_name = _load_font("Almendra-Bold.ttf", 64)
font_blurb = _load_font("MedievalSharp-Oblique.ttf", 36)  # italic, same as monster blurbs


# ═══════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════
COLOR_CREAM = (255, 240, 200)
COLOR_DARK = (30, 15, 5)
COLOR_DARK_BROWN = (60, 35, 10)
COLOR_DIVIDER = (80, 45, 15, 255)


# ═══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def draw_curved_text(
    canvas: Image.Image,
    text: str,
    y_center: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    arc_depth: int = 8,
    x_center: int = CARD_W // 2,
) -> None:
    """Draw text warped along a gentle parabolic arc."""
    tmp = ImageDraw.Draw(canvas)
    bbox = tmp.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_y = abs(arc_depth) + 10
    strip_w = tw + 20
    strip_h = th + pad_y * 2
    strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    text_x = (strip_w - tw) // 2 - bbox[0]
    text_y = pad_y - bbox[1]
    sd.text((text_x, text_y), text, font=font, fill=fill)

    arr = np.array(strip)
    out = np.zeros_like(arr)
    half_w = strip_w / 2.0

    for col in range(strip_w):
        t = (col - half_w) / half_w if half_w else 0.0
        shift = int(round(arc_depth * (1.0 - t * t)))
        if shift >= 0:
            if shift < strip_h:
                out[shift:, col] = arr[:strip_h - shift, col]
        else:
            s = -shift
            if s < strip_h:
                out[:strip_h - s, col] = arr[s:, col]

    warped = Image.fromarray(out, "RGBA")
    paste_x = x_center - strip_w // 2
    paste_y = y_center - strip_h // 2
    canvas.alpha_composite(warped, (paste_x, paste_y))


def _pixel_wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Word-wrap text using actual pixel measurements."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if draw.textlength(trial, font=font) <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


# ═══════════════════════════════════════════════════════════════════════════
# CARD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_card(minion: dict) -> Path:
    """Generate a single minion card and return the output path."""
    portrait_path = PORTRAITS_DIR / minion["portrait"]
    output_path = FINISHED_DIR / minion["output"]

    if not portrait_path.exists():
        print(f"  SKIP — portrait not found: {portrait_path}")
        return output_path

    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    portrait = Image.open(portrait_path).convert("RGBA")

    # Brighten template slightly for readability
    tpl_rgb = template.convert("RGB")
    tpl_bright = ImageEnhance.Brightness(tpl_rgb).enhance(1.08)
    tpl_bright_rgba = tpl_bright.convert("RGBA")
    tpl_bright_rgba.putalpha(template.getchannel("A"))
    template = tpl_bright_rgba

    # --- Portrait placement ---
    pw, ph = portrait.size
    window_w = PORTRAIT_WINDOW_RIGHT - PORTRAIT_WINDOW_LEFT
    window_h = PORTRAIT_WINDOW_BOTTOM - PORTRAIT_WINDOW_TOP

    scale = max(window_w / pw, window_h / ph)
    new_w = int(pw * scale)
    new_h = int(ph * scale)
    portrait_resized = portrait.resize((new_w, new_h), Image.LANCZOS)

    px = PORTRAIT_WINDOW_LEFT + (window_w - new_w) // 2
    py = PORTRAIT_WINDOW_TOP

    canvas = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    canvas.paste(portrait_resized, (px, py))
    canvas = Image.alpha_composite(canvas, template)

    draw = ImageDraw.Draw(canvas)
    text_width = TEXT_AREA_RIGHT - TEXT_AREA_LEFT

    # ------------------------------------------------------------------
    # TOP FRAME — type label and strength
    # ------------------------------------------------------------------
    draw.text(TYPE_LABEL_POS, minion["type"].upper(),
              font=font_type_label, fill=COLOR_CREAM)

    str_text = minion["strength"]
    s_bbox = draw.textbbox((0, 0), str_text, font=font_strength)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text((STRENGTH_POS[0] - s_w // 2, STRENGTH_POS[1]),
              str_text, font=font_strength, fill=COLOR_DARK)

    # ------------------------------------------------------------------
    # NAME BANNER — centred with gentle arc
    # ------------------------------------------------------------------
    name_font = font_name
    NAME_BANNER_HPAD = 60
    max_name_w = CARD_W - NAME_BANNER_HPAD * 2
    banner_h = NAME_BANNER_BOTTOM - NAME_BANNER_TOP

    name_bbox = draw.textbbox((0, 0), minion["name"], font=name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]
    cur_name_size = name_font.size

    while (name_w > max_name_w or name_h > banner_h) and cur_name_size > 20:
        cur_name_size -= 1
        name_font = _load_font("Almendra-Bold.ttf", cur_name_size)
        name_bbox = draw.textbbox((0, 0), minion["name"], font=name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]

    name_y = NAME_BANNER_TOP + (banner_h - name_h) // 2 + 8
    name_y = max(NAME_BANNER_TOP, name_y)
    arc = int(round(-6 - 0.0125 * max(0, name_w - 350)))

    name_y_center = name_y + name_h // 2
    draw_curved_text(canvas, minion["name"], name_y_center, name_font,
                     COLOR_DARK, arc_depth=arc)
    draw = ImageDraw.Draw(canvas)  # refresh after alpha_composite

    # ------------------------------------------------------------------
    # BOTTOM TEXT AREA — blurb only, italic, centred H+V
    # ------------------------------------------------------------------
    blurb_text = minion["blurb"]

    # Auto-scale blurb font if it doesn't fit the width
    blurb_font = font_blurb
    if draw.textlength(blurb_text, font=blurb_font) > text_width:
        blurb_size = blurb_font.size
        while draw.textlength(blurb_text, font=blurb_font) > text_width and blurb_size > 16:
            blurb_size -= 1
            blurb_font = _load_font("MedievalSharp-Oblique.ttf", blurb_size)

    # Measure blurb height (may wrap to multiple lines)
    lines = _pixel_wrap(draw, blurb_text, blurb_font, text_width)
    total_h = 0
    line_heights: list[int] = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=blurb_font)
        lh = int((bbox[3] - bbox[1]) * TEXT_LINE_HEIGHT_FACTOR)
        line_heights.append(lh)
        total_h += lh

    # Centre the blurb + star decorations vertically in the text area
    STAR_PAD = 30  # gap between star row and text
    star_text = "*  *  *"
    star_font = _load_font("MedievalSharp.ttf", 28)
    star_bbox = draw.textbbox((0, 0), star_text, font=star_font)
    star_h = star_bbox[3] - star_bbox[1]

    block_h = star_h + STAR_PAD + total_h + STAR_PAD + star_h
    area_h = TEXT_AREA_BOTTOM - TEXT_AREA_TOP
    block_top = TEXT_AREA_TOP + (area_h - block_h) // 2 - 3

    # Stars above blurb
    star_w = star_bbox[2] - star_bbox[0]
    star_x = TEXT_AREA_LEFT + (text_width - star_w) // 2
    draw.text((star_x, block_top), star_text, font=star_font, fill=COLOR_DARK_BROWN)

    y = block_top + star_h + STAR_PAD

    # Draw each line centred horizontally
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=blurb_font)
        lw = bbox[2] - bbox[0]
        x = TEXT_AREA_LEFT + (text_width - lw) // 2
        draw.text((x, y), line, font=blurb_font, fill=COLOR_DARK_BROWN)
        y += line_heights[i]

    # Stars below blurb
    star_bottom_y = y + STAR_PAD
    draw.text((star_x, star_bottom_y), star_text, font=star_font, fill=COLOR_DARK_BROWN)

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------
    canvas.save(str(output_path), "PNG")
    print(f"  -> {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]

    if not args:
        keys = list(MINIONS.keys())
    else:
        keys = args

    for key in keys:
        if key not in MINIONS:
            print(f"  Unknown minion key: '{key}'")
            print(f"  Available: {', '.join(MINIONS.keys())}")
            continue
        m = MINIONS[key]
        print(f"Generating {m['name']}...")
        generate_card(m)

    print("Done.")


if __name__ == "__main__":
    main()

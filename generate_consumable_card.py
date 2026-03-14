"""
Consumable Card Generator — composites a portrait onto the Equip Card Template,
adds the item name in the name banner, and places the description in the bottom
text area between decorative asterisks:

    *  *  *
    Description (upright)
    *  *  *

All centred horizontally and vertically in the text area.

Usage:
    python generate_consumable_card.py                   # generate ALL consumable cards
    python generate_consumable_card.py vial_shrinkage    # generate one by key
    python generate_consumable_card.py --all             # force-regenerate all
"""

from __future__ import annotations

import numpy as np
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


# ═══════════════════════════════════════════════════════════════════════════
# CONSUMABLE CARD DATA
# ═══════════════════════════════════════════════════════════════════════════

CONSUMABLE_CARDS: dict[str, dict] = {
    "vial_shrinkage": {
        "name": "Vial of Nervous Shrinkage",
        "portrait": "Vial of Nervous Shrinkage.png",
        "output": "Vial of Nervous Shrinkage Card.png",
        "desc": "Give a monster -3 Str.",
    },
    "vial_pool": {
        "name": "Vial Was in the Pool",
        "portrait": "Vial was in the Pool.png",
        "output": "Vial Was in the Pool Card.png",
        "desc": "Give a monster -5 Str.",
    },
    "ice_bath_vial": {
        "name": "Ice Bath Vial",
        "portrait": "Ice Bath Vial.png",
        "output": "Ice Bath Vial Card.png",
        "desc": "Give a monster -7 Str.",
    },
    "potion_minor_embiggening": {
        "name": "Potion of Minor Embiggening",
        "portrait": "Potion of Minor Embiggening.png",
        "output": "Potion of Minor Embiggening Card.png",
        "desc": "Give a monster +3 Str.",
    },
    "potion_moderate_embiggening": {
        "name": "Potion of Moderate Embiggening",
        "portrait": "Potion of Moderate Embiggening.png",
        "output": "Potion of Moderate Embiggening Card.png",
        "desc": "Give a monster +5 Str.",
    },
    "potion_major_embiggening": {
        "name": "Potion of Major Embiggening",
        "portrait": "Potion of Major Embiggening.png",
        "output": "Potion of Major Embiggening Card.png",
        "desc": "Give a monster +7 Str.",
    },
    "h_bomb": {
        "name": "H-Bomb",
        "portrait": "H Bomb.png",
        "output": "H-Bomb Card.png",
        "desc": "Draw a Tier-1 Monster Card and give its curse to a player of your choice.",
    },
    "s_bomb": {
        "name": "S-Bomb",
        "portrait": "S Bomb.png",
        "output": "S-Bomb Card.png",
        "desc": "Draw a Tier-2 Monster Card and give its curse to a player of your choice.",
    },
    "f_bomb": {
        "name": "F-Bomb",
        "portrait": "F Bomb.png",
        "output": "F-Bomb Card.png",
        "desc": "Draw a Tier-3 Monster Card and give its curse to a player of your choice.",
    },
    "priests_blessing": {
        "name": "Priest\u2019s Blessing",
        "portrait": "Priest's Blessing.png",
        "output": "Priest's Blessing Card.png",
        "desc": "Use before playing a movement card. Draw a Tier-1 Monster card to see its Curse. Gain its Trait.",
    },
    "many_priests_blessings": {
        "name": "Many Priests\u2019 Blessings",
        "portrait": "Many Priests' Blessings.png",
        "output": "Many Priests' Blessings Card.png",
        "desc": "Use before playing a movement card. Draw a Tier-2 Monster card to see its Curse. Gain its Trait.",
    },
    "nectar_of_gods": {
        "name": "Nectar of the Gods",
        "portrait": "Nectar of the Gods.png",
        "output": "Nectar of the Gods Card.png",
        "desc": "Draw a Tier-3 Monster Card and gain its Trait.",
    },
    "capture_mk1": {
        "name": "Monster Capture Device Mark I",
        "portrait": "Monster Capture Device Mark 1.png",
        "output": "Monster Capture Device Mark I Card.png",
        "desc": (
            "When fighting a Tier-1 monster, you may play this card to put the monster "
            "in your pack. You receive no trait or curse. You may play the monster while "
            "on an empty square and fight it like normal."
        ),
    },
    "capture_mk2": {
        "name": "Monster Capture Device Mark II",
        "portrait": "Monster Capture Device Mark 2.png",
        "output": "Monster Capture Device Mark II Card.png",
        "desc": (
            "When fighting a Tier-2 monster, you may play this card to put the monster "
            "in your pack. You receive no trait or curse. You may play the monster while "
            "on an empty square and fight it like normal."
        ),
    },
    "capture_mk3": {
        "name": "Monster Capture Device Mark III",
        "portrait": "Monster Capture Device Mark 3.png",
        "output": "Monster Capture Device Mark III Card.png",
        "desc": (
            "When fighting a Tier-3 monster, you may play this card to put the monster "
            "in your pack. You receive no trait or curse. You may play the monster while "
            "on an empty square and fight it like normal."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════
CONSUMABLE_DIR    = Path("Images/Items/Consumables")
PORTRAITS_DIR     = CONSUMABLE_DIR / "Consumable Portraits"
FINISHED_DIR      = CONSUMABLE_DIR / "Consumable Finished Cards"
TEMPLATE_PATH     = Path("Images/Items/Head Armour/Equip card Template.png")


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS  (matches the Equip card template)
# ═══════════════════════════════════════════════════════════════════════════
CARD_W, CARD_H = 1024, 1536

# Portrait window (transparent region in template)
PORTRAIT_WINDOW_TOP    = 230
PORTRAIT_WINDOW_BOTTOM = 1033
PORTRAIT_WINDOW_LEFT   = 48
PORTRAIT_WINDOW_RIGHT  = 1008

# Name banner
NAME_BANNER_TOP    = 115
NAME_BANNER_BOTTOM = 230

# Bottom text area
TEXT_AREA_TOP    = 1070
TEXT_AREA_LEFT   = 142
TEXT_AREA_RIGHT  = 882
TEXT_AREA_BOTTOM = 1470
TEXT_LINE_HEIGHT_FACTOR = 1.30

STAR_PAD = 30  # padding above/below the *** separators


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


font_name              = _load_font("Almendra-Bold.ttf", 64)
font_desc              = _load_font("MedievalSharp.ttf", 36)
DEFAULT_TEXT_FONT_SIZE = 36


# ═══════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════
COLOR_CREAM      = (255, 240, 200)
COLOR_DARK       = (30, 15, 5)
COLOR_DARK_BROWN = (60, 35, 10)


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


def _line_heights(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
) -> list[int]:
    heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        heights.append(int((bbox[3] - bbox[1]) * TEXT_LINE_HEIGHT_FACTOR))
    return heights


# ═══════════════════════════════════════════════════════════════════════════
# CARD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_card(item: dict, force: bool = False) -> Path:
    """Generate a single consumable card and return the output path."""
    portrait_path = PORTRAITS_DIR / item["portrait"]
    output_path   = FINISHED_DIR  / item["output"]

    if not force and output_path.exists():
        print(f"  skip (already exists): {output_path.name}")
        return output_path

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

    # Per-item text font size (default 36, can be overridden)
    txt_size  = item.get("text_font_size", DEFAULT_TEXT_FONT_SIZE)
    f_upright = _load_font("MedievalSharp.ttf", txt_size) if txt_size != DEFAULT_TEXT_FONT_SIZE else font_desc

    # ------------------------------------------------------------------
    # NAME BANNER — centred with gentle arc
    # ------------------------------------------------------------------
    name_font = font_name
    NAME_BANNER_HPAD = 90
    max_name_w = CARD_W - NAME_BANNER_HPAD * 2
    banner_h = NAME_BANNER_BOTTOM - NAME_BANNER_TOP

    name_bbox = draw.textbbox((0, 0), item["name"], font=name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]
    cur_name_size = name_font.size

    while (name_w > max_name_w or name_h > banner_h) and cur_name_size > 20:
        cur_name_size -= 1
        name_font = _load_font("Almendra-Bold.ttf", cur_name_size)
        name_bbox = draw.textbbox((0, 0), item["name"], font=name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]

    name_y = NAME_BANNER_TOP + (banner_h - name_h) // 2 + 8
    name_y = max(NAME_BANNER_TOP, name_y)
    arc = int(round(-7 - 0.025 * max(0, name_w - 300)))

    # The parabolic arc shifts the visual centre upward by ~|arc|/2 px;
    # compensate by nudging the centre point down by that amount.
    arc_compensation = abs(arc) // 2
    name_y_center = name_y + name_h // 2 + arc_compensation
    draw_curved_text(canvas, item["name"], name_y_center, name_font,
                     COLOR_DARK, arc_depth=arc)
    draw = ImageDraw.Draw(canvas)  # refresh after alpha_composite

    # ------------------------------------------------------------------
    # BOTTOM TEXT AREA — ***  /  Description (upright)  /  ***
    #                    Entire block centred vertically in the text area.
    # ------------------------------------------------------------------
    desc_lines = _pixel_wrap(draw, item["desc"], f_upright, text_width)
    desc_lhs   = _line_heights(draw, desc_lines, f_upright)
    desc_total_h = sum(desc_lhs)

    star_text = "*  *  *"
    star_font = _load_font("MedievalSharp.ttf", 28)
    star_bbox = draw.textbbox((0, 0), star_text, font=star_font)
    star_h    = star_bbox[3] - star_bbox[1]
    star_w    = star_bbox[2] - star_bbox[0]
    star_x    = TEXT_AREA_LEFT + (text_width - star_w) // 2

    block_h   = star_h + STAR_PAD + desc_total_h + STAR_PAD + star_h
    area_h    = TEXT_AREA_BOTTOM - TEXT_AREA_TOP
    block_top = TEXT_AREA_TOP + (area_h - block_h) // 2

    draw.text((star_x, block_top), star_text, font=star_font, fill=COLOR_DARK_BROWN)

    y = block_top + star_h + STAR_PAD
    for i, line in enumerate(desc_lines):
        bbox = draw.textbbox((0, 0), line, font=f_upright)
        lw = bbox[2] - bbox[0]
        x = TEXT_AREA_LEFT + (text_width - lw) // 2
        draw.text((x, y), line, font=f_upright, fill=COLOR_DARK_BROWN)
        y += desc_lhs[i]

    draw.text((star_x, y + STAR_PAD), star_text, font=star_font, fill=COLOR_DARK_BROWN)

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------
    FINISHED_DIR.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path), "PNG")
    print(f"  -> {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    raw_args = sys.argv[1:]
    force = "--all" in raw_args
    args = [a.lower() for a in raw_args if a != "--all"]

    if not args:
        print("=== Consumable Cards ===")
        for key, item in CONSUMABLE_CARDS.items():
            print(f"Generating {item['name']}...")
            generate_card(item, force=force)
    else:
        for key in args:
            if key not in CONSUMABLE_CARDS:
                print(f"  Unknown consumable key: '{key}'")
                print(f"  Available: {', '.join(CONSUMABLE_CARDS.keys())}")
                continue
            item = CONSUMABLE_CARDS[key]
            print(f"Generating {item['name']}...")
            generate_card(item, force=force)

    print("Done.")


if __name__ == "__main__":
    main()

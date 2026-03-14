"""
Mini Boss & Werbler Card Generator — composites portraits onto the Monster Card
Template with text overlays for name, type, strength, description, and abilities.

Mini Bosses use:   ABILITY (left) | WEAKNESS (right)
Werblers use:      ABILITY 1 (left) | ABILITY 2 (right)

Usage:
    python generate_boss_card.py                         # generate ALL
    python generate_boss_card.py shielded_golem          # one by key
    python generate_boss_card.py --werblers              # werblers only
    python generate_boss_card.py --minibosses            # minibosses only
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


# ═══════════════════════════════════════════════════════════════════════════
# MINI BOSS DATA
# ═══════════════════════════════════════════════════════════════════════════

MINIBOSSES: dict[str, dict] = {
    # ---- Tier 1 (tile 30) ----
    "shielded_golem": {
        "name": "Shielded Golem",
        "type": "Mini Boss",
        "strength": "+14",
        "level": 1,
        "portrait": "Shielded Golem.png",
        "output": "Shielded Golem Card.png",
        "description": "Not a damn chink.",
        "left_header": "ABILITY",
        "left": {
            "name": "Armoured",
            "text": "Each card you have equipped grants 1 less Str. than normal (minimum 0).",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "Gotta Give \u2019Er",
            "text": "2-Handed Weapons provide 5 additional Str.",
        },
    },
    "flaming_golem": {
        "name": "Flaming Golem",
        "type": "Mini Boss",
        "strength": "+11",
        "level": 1,
        "portrait": "Flaming Golem.png",
        "output": "Flaming Golem Card.png",
        "description": "Now that\u2019s what I call representation!",
        "left_header": "ABILITY",
        "left": {
            "name": "My Fajitas!",
            "text": "Head and chest armour provides 2 less Str. than normal (minimum 0).",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "Ross, Oven Mitts!",
            "text": "If the player is wearing a gauntlet, they win the battle automatically.",
        },
    },
    "ghostly_golem": {
        "name": "Ghostly Golem",
        "type": "Mini Boss",
        "strength": "+13",
        "level": 1,
        "portrait": "Ghostly Golem.png",
        "output": "Ghostly Golem Card.png",
        "description": "They brought it to life\u2026 then it died\u2026 then it came back!",
        "left_header": "ABILITY",
        "left": {
            "name": "Run awaaaaaay!",
            "text": "If you lose to Ghostly Golem, run backwards 10 spaces.",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "I Learned it from Supernatural",
            "text": 'If you have anything with the word "Iron" equipped, you win this fight.',
        },
    },
    "goaaaaaaaalem": {
        "name": "Goaaaaaaaalem",
        "type": "Mini Boss",
        "strength": "+12",
        "level": 1,
        "portrait": "Goaaaaaaaaalem.png",
        "output": "Goaaaaaaaalem Card.png",
        "description": "Fun fact: Soccer was actually the original name!",
        "left_header": "ABILITY",
        "left": {
            "name": "Make a Wall",
            "text": "If you have no free hand slots, you have -5 Str.",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "No Jock",
            "text": "Your Leg Armour has x2 Str. Aim for the groin.",
        },
    },

    # ---- Tier 2 (tile 60) ----
    "sky_dragon": {
        "name": "Sky Dragon",
        "type": "Mini Boss",
        "strength": "+22",
        "level": 2,
        "portrait": "Sky Dragon.png",
        "output": "Sky Dragon Card.png",
        "description": "It\u2019s a bird! It\u2019s a plane! It\u2019s \u2014 uh oh.",
        "left_header": "ABILITY",
        "left": {
            "name": "You Will Not Get This",
            "text": "All weapons except guns provide 0 Str.",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "You Got This",
            "text": "Guns provide +5 Str.",
        },
    },
    "crossroads_demon": {
        "name": "Crossroads Demon",
        "type": "Mini Boss",
        "strength": "+23",
        "level": 2,
        "portrait": "Crossroads Demon.png",
        "output": "Crossroads Demon Card.png",
        "description": "He has the best deals. Nobody knows deals like him.",
        "left_header": "ABILITY",
        "left": {
            "name": "Hypnotic Gaze",
            "text": "If you\u2019re not wearing head armour, you have -10 Str.",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "A Fair Exchange",
            "text": (
                "Before the fight, you may discard as many Equip cards as "
                "you\u2019d like. If you win, draw that many Tier-3 Item cards."
            ),
        },
    },
    "the_watcher": {
        "name": "The Watcher",
        "type": "Mini Boss",
        "strength": "+24",
        "level": 2,
        "portrait": "The Watcher.png",
        "output": "The Watcher Card.png",
        "description": 'Also known as "The Eater", unfortunately.',
        "left_header": "ABILITY",
        "left": {
            "name": "I Consume All",
            "text": "You may not use consumables for this fight.",
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "Call of the Void",
            "text": "All empty Equip slots provide an additional +2 Str. each.",
        },
    },
    "ogre_cutpurse": {
        "name": "Ogre Cutpurse",
        "type": "Mini Boss",
        "strength": "+25",
        "level": 2,
        "portrait": "Ogre Cutpurse.png",
        "output": "Ogre Cutpurse Card.png",
        "description": "Surprisingly stealthy.",
        "left_header": "ABILITY",
        "left": {
            "name": "Sticky Fingers",
            "text": (
                "At combat start, discard all items from your pack. If any "
                "Equip cards are discarded, add their Str. to this monster."
            ),
        },
        "right_header": "WEAKNESS",
        "right": {
            "name": "Travelling Light",
            "text": "If your pack is empty when the fight begins, gain +5 Str.",
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# WERBLER DATA
# ═══════════════════════════════════════════════════════════════════════════

WERBLERS: dict[str, dict] = {
    "brady_the_bicephalous": {
        "name": "Brady the Bicephalous",
        "type": "Werbler",
        "strength": "+40",
        "level": 3,
        "portrait": "Brady the Bicephalous.png",
        "output": "Brady the Bicephalous Card.png",
        "description": "2 heads, plus great biceps.",
        "left_header": "ABILITY",
        "left": {
            "name": "Big and Tall",
            "text": "All melee weapons have -3 Str.",
        },
        "right_header": "ABILITY",
        "right": {
            "name": "Nice Hat",
            "text": (
                "If you lose to Brady, he steals your head armour, "
                "and gains that much Str. permanently (max 2 thefts)."
            ),
        },
    },
    "harry_the_high_elf": {
        "name": "Harry the High Elf",
        "type": "Werbler",
        "strength": "+40",
        "level": 3,
        "portrait": "Harry the High Elf.png",
        "output": "Harry the High Elf Card.png",
        "description": "If you listen closely, you can hear him coughing.",
        "left_header": "ABILITY",
        "left": {
            "name": "Light it up!",
            "text": "Harry has +10 Str. during the day.",
        },
        "right_header": "ABILITY",
        "right": {
            "name": "Tainted",
            "text": "If you lose to Harry, draw a Tier-3 Monster Card and take on its curse.",
        },
    },
    "ar_meg_geddon": {
        "name": "Ar-Meg-Geddon",
        "type": "Werbler",
        "strength": "+40",
        "level": 3,
        "portrait": "Ar-Meg-Geddon.png",
        "output": "Ar-Meg-Geddon Card.png",
        "description": "Hormones are crazy.",
        "left_header": "ABILITY",
        "left": {
            "name": "All-Mother",
            "text": "Your minions refuse to fight her, and do not contribute to your Str.",
        },
        "right_header": "ABILITY",
        "right": {
            "name": "Schmegged",
            "text": "If you lose to Ar-Meg-Geddon, discard anything equipped to your chest and leg slots.",
        },
    },
    "johnil_the_slimelord": {
        "name": "Joh'Neil The Slimelord",
        "type": "Werbler",
        "strength": "+40",
        "level": 3,
        "portrait": "Joh'Neil the Slimelord.png",
        "output": "Joh'Neil The Slimelord Card.png",
        "description": "Yuck.",
        "left_header": "ABILITY",
        "left": {
            "name": "Stretchy",
            "text": "One-handed weapons have -4 Str.",
        },
        "right_header": "ABILITY",
        "right": {
            "name": "Slurp!",
            "text": "If you lose to Joh'Neil, he slurps up your traits. Lose 2 traits of your choice.",
        },
    },
}

ALL_BOSSES = {**MINIBOSSES, **WERBLERS}


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
MINIBOSS_DIR = Path("Images/Mini Bosses")
MINIBOSS_PORTRAITS = MINIBOSS_DIR / "Portraits"
MINIBOSS_FINISHED = MINIBOSS_DIR / "Finished Cards"
MINIBOSS_TEMPLATE = MINIBOSS_DIR / "Monster Card Template.png"

WERBLER_DIR = Path("Images/Werblers")
WERBLER_PORTRAITS = WERBLER_DIR / "Werbler Portraits"
WERBLER_FINISHED = WERBLER_DIR / "Werbler Finished Cards"
WERBLER_TEMPLATE = MINIBOSS_TEMPLATE  # same template

CARD_W, CARD_H = 1024, 1536

# Portrait window (transparent region in template)
PORTRAIT_WINDOW_TOP = 220
PORTRAIT_WINDOW_BOTTOM = 1030
PORTRAIT_WINDOW_LEFT = 48
PORTRAIT_WINDOW_RIGHT = 1008

# Top frame labels
TYPE_LABEL_POS = (160, 55)
STRENGTH_POS = (910, 62)

# Name banner (parchment, y ≈ 115–230)
NAME_BANNER_TOP = 115
NAME_BANNER_BOTTOM = 230

# Bottom text area (parchment)
TEXT_AREA_TOP = 1060
TEXT_AREA_LEFT = 100
TEXT_AREA_RIGHT = 924
TEXT_AREA_BOTTOM = 1480
TEXT_LINE_HEIGHT_FACTOR = 1.30

# Two-column layout
COLUMN_GAP = 30
DIVIDER_X = CARD_W // 2

LEFT_COL_LEFT = TEXT_AREA_LEFT
LEFT_COL_RIGHT = DIVIDER_X - COLUMN_GAP // 2
RIGHT_COL_LEFT = DIVIDER_X + COLUMN_GAP // 2
RIGHT_COL_RIGHT = TEXT_AREA_RIGHT


# ═══════════════════════════════════════════════════════════════════════════
# FONTS
# ═══════════════════════════════════════════════════════════════════════════
FONT_DIR = Path(r"C:\Windows\Fonts")


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
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


font_type_label = _load_font("Cinzel-Black.ttf", 38)
font_strength = _load_font("Cinzel-Black.ttf", 56)
font_name = _load_font("Almendra-Bold.ttf", 64)
font_description = _load_font("MedievalSharp-Oblique.ttf", 30)
font_section_title = _load_font("Cinzel-Black.ttf", 30)
font_ability_name = _load_font("MedievalSharp-Bold.ttf", 32)
font_ability_text = _load_font("MedievalSharp.ttf", 30)

# ═══════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════
COLOR_CREAM = (255, 240, 200)
COLOR_DARK = (30, 15, 5)
COLOR_DARK_BROWN = (60, 35, 10)
COLOR_TRAIT_HEADER = (30, 85, 25)
COLOR_TRAIT_NAME = (75, 115, 70)
COLOR_CURSE_HEADER = (130, 25, 15)
COLOR_CURSE_NAME = (155, 65, 55)
COLOR_DIVIDER = (80, 45, 15, 255)

# Abilities are red; weaknesses are green (opposite of trait/curse convention)
COLOR_ABILITY_HEADER = COLOR_CURSE_HEADER
COLOR_ABILITY_NAME = COLOR_CURSE_NAME
COLOR_WEAKNESS_HEADER = COLOR_TRAIT_HEADER
COLOR_WEAKNESS_NAME = COLOR_TRAIT_NAME


# ═══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS (identical to generate_monster_card.py)
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


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_width: int,
    line_height_factor: float = TEXT_LINE_HEIGHT_FACTOR,
    center: bool = False,
    x_left: int = TEXT_AREA_LEFT,
    dry_run: bool = False,
) -> int:
    lines = _pixel_wrap(draw, text, font, max_width)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lh = int((bbox[3] - bbox[1]) * line_height_factor)
        if not dry_run:
            if center:
                lw = bbox[2] - bbox[0]
                x = x_left + (max_width - lw) // 2
            else:
                x = x_left
            draw.text((x, y), line, font=font, fill=fill)
        y += lh
    return y


def measure_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    line_height_factor: float = TEXT_LINE_HEIGHT_FACTOR,
) -> int:
    return draw_wrapped_text(
        draw, text, 0, font, (0, 0, 0), max_width,
        line_height_factor=line_height_factor,
        dry_run=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CARD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_card(boss: dict) -> Path:
    """Generate a single mini-boss or werbler card and return the output path."""
    is_werbler = boss["type"].lower() == "werbler"

    if is_werbler:
        portrait_dir = WERBLER_PORTRAITS
        finished_dir = WERBLER_FINISHED
        template_path = WERBLER_TEMPLATE
    else:
        portrait_dir = MINIBOSS_PORTRAITS
        finished_dir = MINIBOSS_FINISHED
        template_path = MINIBOSS_TEMPLATE

    portrait_path = portrait_dir / boss["portrait"]
    output_path = finished_dir / boss["output"]

    if not portrait_path.exists():
        print(f"  SKIP — portrait not found: {portrait_path}")
        return output_path

    template = Image.open(template_path).convert("RGBA")
    portrait = Image.open(portrait_path).convert("RGBA")

    if "portrait_brightness" in boss:
        p_rgb = portrait.convert("RGB")
        p_bright = ImageEnhance.Brightness(p_rgb).enhance(boss["portrait_brightness"])
        p_bright_rgba = p_bright.convert("RGBA")
        p_bright_rgba.putalpha(portrait.getchannel("A"))
        portrait = p_bright_rgba

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

    # --- Top frame: type label and strength ---
    draw.text(TYPE_LABEL_POS, boss["type"].upper(),
              font=font_type_label, fill=COLOR_CREAM)

    str_text = boss["strength"]
    s_bbox = draw.textbbox((0, 0), str_text, font=font_strength)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text((STRENGTH_POS[0] - s_w // 2, STRENGTH_POS[1]),
              str_text, font=font_strength, fill=COLOR_DARK)

    # --- Name banner ---
    hero_name_font = font_name
    NAME_BANNER_HPAD = 60
    max_name_w = CARD_W - NAME_BANNER_HPAD * 2
    banner_h = NAME_BANNER_BOTTOM - NAME_BANNER_TOP

    name_bbox = draw.textbbox((0, 0), boss["name"], font=hero_name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]
    cur_name_size = hero_name_font.size

    while (name_w > max_name_w or name_h > banner_h) and cur_name_size > 20:
        cur_name_size -= 1
        hero_name_font = _load_font("Almendra-Bold.ttf", cur_name_size)
        name_bbox = draw.textbbox((0, 0), boss["name"], font=hero_name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]

    long_offset = int(round(0.012 * max(0, name_w - 500)))
    name_y = NAME_BANNER_TOP + (banner_h - name_h) // 2 + 3 + long_offset
    name_y = max(NAME_BANNER_TOP, name_y)
    arc = int(round(-5 - 0.018 * max(0, name_w - 500)))

    name_y_center = name_y + name_h // 2
    draw_curved_text(canvas, boss["name"], name_y_center, hero_name_font,
                     COLOR_DARK, arc_depth=arc)
    draw = ImageDraw.Draw(canvas)

    # --- Bottom text area ---
    text_width = TEXT_AREA_RIGHT - TEXT_AREA_LEFT
    left_col_w = LEFT_COL_RIGHT - LEFT_COL_LEFT
    right_col_w = RIGHT_COL_RIGHT - RIGHT_COL_LEFT

    BLURB_PAD = 20
    _ref_bbox = draw.textbbox((0, 0), "Xg", font=font_description)
    _ref_h = int((_ref_bbox[3] - _ref_bbox[1]) * TEXT_LINE_HEIGHT_FACTOR)
    HRULE_Y = TEXT_AREA_TOP + BLURB_PAD + _ref_h + BLURB_PAD

    # --- Description blurb ---
    desc_text = boss["description"]
    desc_y = TEXT_AREA_TOP + BLURB_PAD - 3
    desc_font = font_description
    if draw.textlength(desc_text, font=desc_font) > text_width:
        desc_size = desc_font.size
        while draw.textlength(desc_text, font=desc_font) > text_width and desc_size > 16:
            desc_size -= 1
            desc_font = _load_font("MedievalSharp-Oblique.ttf", desc_size)
    draw_wrapped_text(
        draw, desc_text, desc_y,
        desc_font, COLOR_DARK_BROWN, text_width,
        center=True, x_left=TEXT_AREA_LEFT,
    )

    # --- Horizontal rule ---
    hrule_y = HRULE_Y
    draw.line(
        [(TEXT_AREA_LEFT, hrule_y), (TEXT_AREA_RIGHT, hrule_y)],
        fill=COLOR_DIVIDER, width=2,
    )
    y = hrule_y + 14

    columns_zone_top = y
    NAME_TO_TEXT_GAP = 12
    HEADER_TO_NAME_GAP = 28

    left_data = boss["left"]
    right_data = boss["right"]
    left_header = boss.get("left_header", "ABILITY")
    right_header = boss.get("right_header", "ABILITY")

    # --- Pick header/name colours based on labels ---
    if left_header == "ABILITY":
        lh_color = COLOR_ABILITY_HEADER
        ln_color = COLOR_ABILITY_NAME
    else:
        lh_color = COLOR_CURSE_HEADER
        ln_color = COLOR_CURSE_NAME

    if right_header == "WEAKNESS":
        rh_color = COLOR_WEAKNESS_HEADER
        rn_color = COLOR_WEAKNESS_NAME
    else:
        rh_color = COLOR_ABILITY_HEADER
        rn_color = COLOR_ABILITY_NAME

    # --- Measure columns ---
    th_bbox = draw.textbbox((0, 0), "ABILITY", font=font_section_title)
    th_h = th_bbox[3] - th_bbox[1]

    def _measure_column(name_text: str, body_text: str, col_w: int) -> int:
        h = th_h + HEADER_TO_NAME_GAP
        h = measure_wrapped(draw, name_text, font_ability_name, col_w) + h
        h += NAME_TO_TEXT_GAP
        h = measure_wrapped(draw, body_text, font_ability_text, col_w) + h
        return h

    left_h = _measure_column(left_data["name"], left_data["text"], left_col_w)
    right_h = _measure_column(right_data["name"], right_data["text"], right_col_w)
    tallest = max(left_h, right_h)

    available = TEXT_AREA_BOTTOM - columns_zone_top
    top_pad = max(0, (available - tallest) // 5)
    y = columns_zone_top + top_pad

    # --- Left header ---
    lh_bbox = draw.textbbox((0, 0), left_header, font=font_section_title)
    lh_w = lh_bbox[2] - lh_bbox[0]
    lh_x = LEFT_COL_LEFT + (left_col_w - lh_w) // 2
    draw.text((lh_x, y), left_header, font=font_section_title, fill=lh_color)

    # --- Right header ---
    rh_bbox = draw.textbbox((0, 0), right_header, font=font_section_title)
    rh_w = rh_bbox[2] - rh_bbox[0]
    rh_x = RIGHT_COL_LEFT + (right_col_w - rh_w) // 2
    draw.text((rh_x, y), right_header, font=font_section_title, fill=rh_color)

    y += th_h + HEADER_TO_NAME_GAP

    # --- Left column ---
    left_y = y
    left_y = draw_wrapped_text(
        draw, left_data["name"], left_y,
        font_ability_name, ln_color, left_col_w,
        center=True, x_left=LEFT_COL_LEFT,
    )
    left_y += NAME_TO_TEXT_GAP
    draw_wrapped_text(
        draw, left_data["text"], left_y,
        font_ability_text, COLOR_DARK, left_col_w,
        center=True, x_left=LEFT_COL_LEFT,
    )

    # --- Right column ---
    right_y = y
    right_y = draw_wrapped_text(
        draw, right_data["name"], right_y,
        font_ability_name, rn_color, right_col_w,
        center=True, x_left=RIGHT_COL_LEFT,
    )
    right_y += NAME_TO_TEXT_GAP
    draw_wrapped_text(
        draw, right_data["text"], right_y,
        font_ability_text, COLOR_DARK, right_col_w,
        center=True, x_left=RIGHT_COL_LEFT,
    )

    # --- Vertical divider ---
    col_bottom = TEXT_AREA_BOTTOM - 6
    divider_color_light = (COLOR_DIVIDER[0], COLOR_DIVIDER[1], COLOR_DIVIDER[2], 160)
    draw.rectangle(
        [(DIVIDER_X, hrule_y), (DIVIDER_X + 1, col_bottom)],
        fill=divider_color_light,
    )

    # --- Save ---
    finished_dir.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path), "PNG")
    print(f"  -> {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]

    if not args:
        keys = list(ALL_BOSSES.keys())
    elif "--werblers" in args:
        keys = list(WERBLERS.keys())
    elif "--minibosses" in args:
        keys = list(MINIBOSSES.keys())
    else:
        keys = args

    for key in keys:
        if key not in ALL_BOSSES:
            print(f"  Unknown key: '{key}'")
            print(f"  Available: {', '.join(ALL_BOSSES.keys())}")
            continue
        boss = ALL_BOSSES[key]
        print(f"Generating {boss['name']}...")
        generate_card(boss)

    print("Done.")


if __name__ == "__main__":
    main()

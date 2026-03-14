"""
Hero Card Generator — composites a portrait onto the Hero Card Template,
adds text overlays for hero name, type, strength, and abilities.

All layout, font, colour, and spacing settings are finalised and should
not need further tuning.  To generate a card for a new hero, add an
entry to HEROES below and place the portrait PNG in Images/Heroes/.

Usage:
    python generate_hero_card.py                  # generate ALL heroes
    python generate_hero_card.py billfold         # generate one hero by key
    python generate_hero_card.py gregory brunhilde # generate specific heroes
"""

from __future__ import annotations

import numpy as np
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# ═══════════════════════════════════════════════════════════════════════════
# HERO DATA — add new heroes here
# ═══════════════════════════════════════════════════════════════════════════
# Each key is a short identifier used on the command line.
# Fields:
#   name          — display name (centred in the name banner)
#   type          — card type label, top-left blue band (usually "Hero")
#   strength      — strength string, top-right gold flap (e.g. "+1")
#   portrait      — filename of the portrait PNG in Images/Heroes/
#   output        — filename for the generated card PNG
#   abilities     — list of {name, text} dicts

HEROES: dict[str, dict] = {
    "billfold": {
        "name": "Billfold Baggains",
        "type": "Hero",
        "strength": "+1",
        "portrait": "Billfold Baggains Portrait.png",
        "output": "Billfold Baggains Card.png",
        "abilities": [
            {
                "name": "Merchant's Eye",
                "text": "When using a Shop, choose from 4 items instead of 3.",
            },
            {
                "name": "Fly, you dummy!",
                "text": (
                    "You may flee from any Monster or Miniboss battle, "
                    "receiving no curse. If you do, you must move back 8 "
                    "spaces (minimum tile 1). Cannot flee The Werbler."
                ),
            },
        ],
    },
    "gregory": {
        "name": "Gregory",
        "type": "Hero",
        "strength": "+1",
        "portrait": "Gregory Portrait.png",
        "output": "Gregory Card.png",
        "abilities": [
            {
                "name": "A Strong Offense",
                "text": (
                    "May equip 4 total weapon hands instead of 2, "
                    "but chest armour does not fit (0 chest armour slots)."
                ),
            },
            {
                "name": "Contagious Mutagen",
                "text": (
                    "Once per game, you may remove one curse of your "
                    "choice from yourself and give it to any other player."
                ),
            },
        ],
    },
    "brunhilde": {
        "name": "Brunhilde the Bodacious",
        "type": "Hero",
        "strength": "+1",
        "portrait": "Brunhilde the Bodacious Portrait.png",
        "output": "Brunhilde the Bodacious Card.png",
        "abilities": [
            {
                "name": "Luscious Locks",
                "text": (
                    "Feel the breeze in your hair! When wearing no "
                    "headgear, gain +5 Str."
                ),
            },
            {
                "name": "Skimpy Armour",
                "text": (
                    "All chest armour gives you a minimum of +8 Str "
                    "(if the armour's printed bonus is higher, use that "
                    "instead). However, if you lose a battle, your current "
                    "chest armour is shredded and must be discarded."
                ),
            },
        ],
    },
    "rizzt": {
        "name": "Rizzt No'Cappin",
        "type": "Hero",
        "strength": "+1",
        "portrait": "Rizzt No'Cappin Portrait.png",
        "output": "Rizzt No'Cappin Card.png",
        "abilities": [
            {
                "name": "IckingUnalive",
                "text": (
                    "You start the game with one copy of "
                    "\"Dark Elf's Scimitar\" equipped."
                ),
            },
            {
                "name": "Night Stalker",
                "text": "During Night, gain +3 Strength in combat.",
            },
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS  (finalised — do not change unless template changes)
# ═══════════════════════════════════════════════════════════════════════════
HEROES_DIR = Path("Images/Heroes")
TEMPLATE_PATH = HEROES_DIR / "Hero Card Template.png"

CARD_W, CARD_H = 1024, 1536

# Portrait window (transparent region in template)
PORTRAIT_WINDOW_TOP = 230      # flush with the name banner bottom
PORTRAIT_WINDOW_BOTTOM = 1033
PORTRAIT_WINDOW_LEFT = 48
PORTRAIT_WINDOW_RIGHT = 1008

# Top frame
TYPE_LABEL_POS = (160, 55)       # "Hero" in the blue band
STRENGTH_POS = (910, 62)         # strength in the gold flap

# Name banner (parchment, y = 115-230)
NAME_BANNER_TOP = 115
NAME_BANNER_BOTTOM = 230

# Bottom text area (parchment)
TEXT_AREA_TOP = 1070
TEXT_AREA_LEFT = 142
TEXT_AREA_RIGHT = 882
TEXT_AREA_BOTTOM = 1470
TEXT_LINE_HEIGHT_FACTOR = 1.35

# ═══════════════════════════════════════════════════════════════════════════
# FONTS
# ═══════════════════════════════════════════════════════════════════════════
FONT_DIR = Path(r"C:\Windows\Fonts")


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by filename, falling back to Arial.

    Searches the system fonts dir and the project root.
    """
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
font_abilities_title = _load_font("Cinzel-Black.ttf", 38)
font_ability_name = _load_font("MedievalSharp-Bold.ttf", 36)
font_ability_text = _load_font("MedievalSharp.ttf", 30)

# ═══════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════
COLOR_CREAM = (255, 240, 200)
COLOR_DARK = (30, 15, 5)
COLOR_DARK_BROWN = (60, 35, 10)
COLOR_ABILITY_NAME = (100, 45, 10)

# ═══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    x_center: int = CARD_W // 2,
) -> int:
    """Draw text horizontally centred. Returns the bottom y."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x_center - tw // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + th


def draw_curved_text(
    canvas: Image.Image,
    text: str,
    y_center: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    arc_depth: int = 8,
    x_center: int = CARD_W // 2,
) -> None:
    """Draw text warped along a gentle parabolic arc.

    Renders the full string flat, then displaces each pixel row by a
    parabolic offset so the text follows the curve of the banner.

    Parameters
    ----------
    canvas : RGBA image to composite onto (modified in-place).
    text : The string to render.
    y_center : Vertical centre-line for the text (before arc).
    font : Font to use.
    fill : Colour tuple.
    arc_depth : Positive = dips down in the middle.  Negative = arcs up.
    x_center : Horizontal centre of the text on the card.
    """
    # 1. Measure the text
    tmp = ImageDraw.Draw(canvas)
    bbox = tmp.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # 2. Render text flat onto an oversized transparent strip
    pad_y = abs(arc_depth) + 10  # vertical room for the warp
    strip_w = tw + 20  # small horizontal margin
    strip_h = th + pad_y * 2
    strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    text_x = (strip_w - tw) // 2 - bbox[0]
    text_y = pad_y - bbox[1]
    sd.text((text_x, text_y), text, font=font, fill=fill)

    # 3. Warp: shift each column vertically by a parabolic amount
    arr = np.array(strip)
    out = np.zeros_like(arr)
    half_w = strip_w / 2.0

    for col in range(strip_w):
        # Normalised position: -1 at left, 0 at centre, +1 at right
        t = (col - half_w) / half_w if half_w else 0.0
        # Parabola: max displacement at centre (t=0), zero at edges (t=±1)
        shift = int(round(arc_depth * (1.0 - t * t)))
        # Shift column pixels
        if shift >= 0:
            if shift < strip_h:
                out[shift:, col] = arr[:strip_h - shift, col]
        else:
            s = -shift
            if s < strip_h:
                out[:strip_h - s, col] = arr[s:, col]

    warped = Image.fromarray(out, "RGBA")

    # 4. Composite onto canvas, centred at (x_center, y_center)
    paste_x = x_center - strip_w // 2
    paste_y = y_center - strip_h // 2
    canvas.alpha_composite(warped, (paste_x, paste_y))


def _pixel_wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Word-wrap *text* using actual pixel measurements."""
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
    font_name: str | None = None,
    min_font_size: int = 20,
    dry_run: bool = False,
) -> int:
    """Pixel-accurate word-wrap with smart anti-orphan.

    If the last line is very short (<=4 chars, e.g. a dangling "3."),
    the font is shrunk 1 pt at a time until the text fits in fewer lines.

    If *dry_run* is True, nothing is drawn — only the final y is returned
    (useful for measuring total height before committing).
    """
    current_font = font
    current_size = font.size

    lines = _pixel_wrap(draw, text, current_font, max_width)

    # Anti-orphan
    if font_name and len(lines) > 1 and len(lines[-1]) <= 4:
        target = len(lines) - 1
        for sz in range(current_size - 1, min_font_size - 1, -1):
            trial_font = _load_font(font_name, sz)
            trial_lines = _pixel_wrap(draw, text, trial_font, max_width)
            if len(trial_lines) <= target:
                current_font = trial_font
                lines = trial_lines
                break

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=current_font)
        lh = int((bbox[3] - bbox[1]) * line_height_factor)
        if not dry_run:
            if center:
                lw = bbox[2] - bbox[0]
                x = x_left + (max_width - lw) // 2
            else:
                x = x_left
            draw.text((x, y), line, font=current_font, fill=fill)
        y += lh
    return y


def _measure_abilities(
    draw: ImageDraw.ImageDraw,
    abilities: list[dict],
    text_width: int,
    ability_name_font: ImageFont.FreeTypeFont,
    ability_text_font: ImageFont.FreeTypeFont,
    name_gap: int = 6,
) -> int:
    """Measure total height of all abilities (no spacing between them)."""
    total = 0
    for ability in abilities:
        # Ability name
        h = draw_wrapped_text(
            draw, ability["name"], 0,
            ability_name_font, (0, 0, 0), text_width,
            center=True, dry_run=True,
        )
        total += h + name_gap
        # Ability text
        h = draw_wrapped_text(
            draw, ability["text"], 0,
            ability_text_font, (0, 0, 0), text_width,
            center=True, font_name="MedievalSharp.ttf", dry_run=True,
        )
        total += h
    return total


def _draw_abilities(
    draw: ImageDraw.ImageDraw,
    y: int,
    abilities: list[dict],
    text_width: int,
    ability_name_font: ImageFont.FreeTypeFont,
    ability_text_font: ImageFont.FreeTypeFont,
    between_gap: int,
    name_gap: int = 6,
) -> int:
    """Render abilities with a given gap between each ability block."""
    for i, ability in enumerate(abilities):
        y = draw_wrapped_text(
            draw, ability["name"], y,
            ability_name_font, COLOR_ABILITY_NAME, text_width,
            center=True,
        )
        y += name_gap
        y = draw_wrapped_text(
            draw, ability["text"], y,
            ability_text_font, COLOR_DARK, text_width,
            center=True,
            font_name="MedievalSharp.ttf",
        )
        if i < len(abilities) - 1:
            y += between_gap
    return y


# ═══════════════════════════════════════════════════════════════════════════
# CARD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_card(hero: dict) -> Path:
    """Generate a single hero card and return the output path."""
    portrait_path = HEROES_DIR / hero["portrait"]
    output_path = HEROES_DIR / hero["output"]

    if not portrait_path.exists():
        print(f"  SKIP — portrait not found: {portrait_path}")
        return output_path

    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    portrait = Image.open(portrait_path).convert("RGBA")

    # Brighten the template (frame, text areas) slightly for readability
    # but leave the portrait untouched.
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
    py = PORTRAIT_WINDOW_TOP  # top-align so head isn't cut off

    canvas = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    canvas.paste(portrait_resized, (px, py))
    canvas = Image.alpha_composite(canvas, template)

    # --- Text overlays ---
    draw = ImageDraw.Draw(canvas)
    text_width = TEXT_AREA_RIGHT - TEXT_AREA_LEFT

    # Type label — top-left blue band
    draw.text(TYPE_LABEL_POS, hero["type"].upper(),
              font=font_type_label, fill=COLOR_CREAM)

    # Strength — top-right gold flap
    s_bbox = draw.textbbox((0, 0), hero["strength"], font=font_strength)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text((STRENGTH_POS[0] - s_w // 2, STRENGTH_POS[1]),
              hero["strength"], font=font_strength, fill=COLOR_DARK)

    # Name — centred vertically & horizontally in banner
    # Allow per-hero font override via optional "name_font" key
    if "name_font" in hero:
        nf_file, nf_size = hero["name_font"]
        hero_name_font = _load_font(nf_file, nf_size)
    else:
        hero_name_font = font_name

    # Auto-shrink: reduce font size until name fits within banner bounds
    NAME_BANNER_HPAD = 60  # horizontal padding each side
    max_name_w = CARD_W - NAME_BANNER_HPAD * 2
    banner_h = NAME_BANNER_BOTTOM - NAME_BANNER_TOP
    cur_name_size = hero_name_font.size
    cur_font_file = hero.get("name_font", ("Almendra-Bold.ttf",))[0]

    name_bbox = draw.textbbox((0, 0), hero["name"], font=hero_name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]

    while (name_w > max_name_w or name_h > banner_h) and cur_name_size > 20:
        cur_name_size -= 1
        hero_name_font = _load_font(cur_font_file, cur_name_size)
        name_bbox = draw.textbbox((0, 0), hero["name"], font=hero_name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]

    name_y = (NAME_BANNER_TOP
              + (banner_h - name_h) // 2
              + 8)
    # Clamp so name never goes above the banner
    name_y = max(NAME_BANNER_TOP, name_y)
    # Scale arc depth: base -6 for short names, grows gently for wider ones
    arc = int(round(-6 - 0.0125 * max(0, name_w - 350)))
    # Draw name along a gentle downward arc matching the banner curve
    name_y_center = name_y + name_h // 2
    draw_curved_text(canvas, hero["name"], name_y_center, hero_name_font,
                     COLOR_DARK, arc_depth=arc)
    # Re-create draw context after alpha_composite calls in draw_curved_text
    draw = ImageDraw.Draw(canvas)

    # --- Bottom text area ---
    # "Abilities" heading + underline
    ab_text = "Abilities"
    ab_bbox = draw.textbbox((0, 0), ab_text, font=font_abilities_title)
    ab_tw = ab_bbox[2] - ab_bbox[0]
    ab_th = ab_bbox[3] - ab_bbox[1]

    # Heading flush with top; small matching gap below text → underline
    heading_underline_gap = 8
    underline_y = TEXT_AREA_TOP + ab_th + heading_underline_gap
    # Centre the heading text between TEXT_AREA_TOP and the underline
    # Subtract extra for optical centering (font descenders make it look low)
    # +5 adds 5 px breathing room above the text
    ab_y = TEXT_AREA_TOP + (underline_y - TEXT_AREA_TOP - ab_th) // 2 - ab_bbox[1] - 8 + 5
    ab_x = CARD_W // 2 - ab_tw // 2
    draw.text((ab_x, ab_y), ab_text, font=font_abilities_title,
              fill=COLOR_DARK_BROWN)
    # Push underline down 5 px for matching breathing room below text
    underline_y += 5
    draw.line(
        [(TEXT_AREA_LEFT, underline_y), (TEXT_AREA_RIGHT, underline_y)],
        fill=COLOR_DARK_BROWN + (255,), width=3,
    )
    y = underline_y + heading_underline_gap  # same gap below underline

    # --- Abilities with dynamic spacing (fixed font size) ---
    abilities = hero["abilities"]
    abilities_start_y = y
    available_h = TEXT_AREA_BOTTOM - abilities_start_y

    MIN_ABILITY_GAP = 18  # minimum gap between ability blocks

    content_h = _measure_abilities(
        draw, abilities, text_width, font_ability_name, font_ability_text,
    )

    # Calculate spacing: distribute remaining space evenly
    num_gaps = max(1, len(abilities) - 1)
    extra_space = available_h - content_h
    # Space between abilities (at least MIN_ABILITY_GAP, distributed evenly)
    between_gap = max(MIN_ABILITY_GAP, extra_space // (num_gaps + 1))
    # Also add top padding to vertically centre the block
    top_pad = (available_h - content_h - between_gap * num_gaps) // 2
    top_pad = max(0, min(top_pad, between_gap))  # cap so it doesn't push too far
    y = abilities_start_y + top_pad

    _draw_abilities(
        draw, y, abilities, text_width,
        font_ability_name, font_ability_text, between_gap,
    )

    # Save
    canvas.save(str(output_path), "PNG")
    print(f"  -> {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]

    if not args:
        # Generate all heroes that have portraits available
        keys = list(HEROES.keys())
    else:
        keys = args

    for key in keys:
        if key not in HEROES:
            print(f"  Unknown hero key: '{key}'")
            print(f"  Available: {', '.join(HEROES.keys())}")
            continue
        hero = HEROES[key]
        print(f"Generating {hero['name']}...")
        generate_card(hero)

    print("Done.")


if __name__ == "__main__":
    main()

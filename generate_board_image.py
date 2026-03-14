"""generate_board_image.py

Composites a randomized Werblers tile grid onto the board background image.

The 10×9 grid uses a snake/boustrophedon path matching the web UI layout:
  - Tile 1  → bottom-left
  - Tile 10 → bottom-right
  - Tile 11 → second row, right (snake reverses direction each row)
  - Tile 90 → top-right (Werbler)

Usage:
    python generate_board_image.py [options]

Options:
    --seed N         Random seed for tile layout (default: random)
    --reveal         Show all tile types (default: all tiles hidden)
    --no-board       Composite onto a plain dark background instead of the board image
    --output PATH    Output file path (default: board_out.png)
    --grid-x X       Left edge of the grid area in pixels (default: auto-centred)
    --grid-y Y       Top edge of the grid area in pixels (default: auto-centred)
    --grid-w W       Total width of the grid area in pixels (default: image width minus 2 * padding)
    --grid-h H       Total height of the grid area in pixels (default: image height minus 2 * padding)
    --padding P      Padding from image edges when auto-sizing (default: 50)
    --tile-alpha A   Tile opacity 0–255 (default: 220)
"""

import argparse
import os
import random
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
TILES_DIR = ROOT / "Images" / "Tiles"
BOARD_IMG = ROOT / "Images" / "Assorted UI Images" / "Werblers Board.png"

# Tile type → image filename inside TILES_DIR
TILE_IMAGES = {
    "CHEST":     "Chest Tile.png",
    "MONSTER":   "Monster Tile.png",
    "SHOP":      "Shop Tile.jpg",
    "BLANK":     "Blank Tile.png",
    "DAY_NIGHT": "Day and Night Tile.png",
    "HIDDEN":    "Hidden Tile.png",
    # Fixed tiles
    "MINIBOSS_1":  "Mini Boss 1.png",
    "MINIBOSS_2":  "Mini Boss 2 Tile.png",
    "WERBLER":     "Werbler Tile.png",
}

# ---------------------------------------------------------------------------
# Board layout (mirrors werblers_engine/board.py)
# ---------------------------------------------------------------------------
FIXED_TILES = {30: "MINIBOSS_1", 60: "MINIBOSS_2", 90: "WERBLER"}

TILE_POOL_COUNTS = [
    ("MONSTER",   16),
    ("CHEST",     28),
    ("SHOP",      15),
    ("BLANK",     15),
    ("DAY_NIGHT", 13),
]

def generate_tile_layout(seed=None):
    """Return a dict {tile_number: type_str} for tiles 1–90."""
    rng = random.Random(seed)
    pool = []
    for tile_type, count in TILE_POOL_COUNTS:
        pool.extend([tile_type] * count)
    assert len(pool) == 87
    rng.shuffle(pool)
    pool_iter = iter(pool)
    layout = {}
    for i in range(1, 91):
        if i in FIXED_TILES:
            layout[i] = FIXED_TILES[i]
        else:
            layout[i] = next(pool_iter)
    return layout


# ---------------------------------------------------------------------------
# Grid geometry (mirrors tileToGrid in game.js)
# ---------------------------------------------------------------------------
def tile_to_grid(n):
    """Return (row, col) in the 10×9 grid, row 0 = top, col 0 = left."""
    row_from_bottom = (n - 1) // 10
    col_in_row = (n - 1) % 10
    row = 8 - row_from_bottom
    col = col_in_row if row_from_bottom % 2 == 0 else 9 - col_in_row
    return row, col


# ---------------------------------------------------------------------------
# Image cache
# ---------------------------------------------------------------------------
_img_cache: dict[str, Image.Image] = {}

def load_tile_image(type_str, tile_size):
    cache_key = f"{type_str}_{tile_size}"
    if cache_key not in _img_cache:
        filename = TILE_IMAGES[type_str]
        img = Image.open(TILES_DIR / filename).convert("RGBA")
        img = img.resize((tile_size, tile_size), Image.LANCZOS)
        _img_cache[cache_key] = img
    return _img_cache[cache_key]


# ---------------------------------------------------------------------------
# Main compositing
# ---------------------------------------------------------------------------
def build_board_image(seed=None, reveal=False, use_board_bg=True,
                      grid_x=None, grid_y=None, grid_w=None, grid_h=None,
                      padding=50, tile_alpha=220, output="board_out.png"):

    # --- Background ---
    if use_board_bg and BOARD_IMG.exists():
        bg = Image.open(BOARD_IMG).convert("RGBA")
        print(f"Board background: {BOARD_IMG.name}  ({bg.width}×{bg.height})")
    else:
        if use_board_bg:
            print(f"Warning: board image not found at {BOARD_IMG}, using plain background.")
        bg = Image.new("RGBA", (1536, 1024), (30, 20, 40, 255))
        print("Using plain dark background (1536×1024)")

    img_w, img_h = bg.size

    # --- Grid area ---
    if grid_w is None:
        grid_w = img_w - 2 * padding
    if grid_h is None:
        grid_h = img_h - 2 * padding

    # Tile size: largest square tile that fits 10 cols and 9 rows
    tile_size = min(grid_w // 10, grid_h // 9)

    # Actual rendered grid pixel dimensions
    actual_grid_w = tile_size * 10
    actual_grid_h = tile_size * 9

    # Auto-centre if not specified
    if grid_x is None:
        grid_x = (img_w - actual_grid_w) // 2
    if grid_y is None:
        grid_y = (img_h - actual_grid_h) // 2

    print(f"Tile size: {tile_size}×{tile_size} px")
    print(f"Grid top-left: ({grid_x}, {grid_y})  →  {actual_grid_w}×{actual_grid_h} px")
    print(f"Seed: {seed}  |  Reveal: {reveal}")

    # --- Generate layout ---
    layout = generate_tile_layout(seed)

    # --- Composite overlay layer ---
    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))

    for tile_num, type_str in layout.items():
        display_type = type_str if reveal else "HIDDEN"
        # Always show fixed landmark tiles regardless of reveal flag
        if tile_num in FIXED_TILES:
            display_type = type_str

        row, col = tile_to_grid(tile_num)
        px = grid_x + col * tile_size
        py = grid_y + row * tile_size

        tile_img = load_tile_image(display_type, tile_size).copy()

        # Apply alpha
        if tile_alpha < 255:
            r, g, b, a = tile_img.split()
            a = a.point(lambda v: int(v * tile_alpha / 255))
            tile_img = Image.merge("RGBA", (r, g, b, a))

        overlay.paste(tile_img, (px, py), tile_img)

    # --- Draw tile numbers (small label) ---
    try:
        from PIL import ImageFont
        font = ImageFont.load_default(size=max(8, tile_size // 8))
    except Exception:
        font = None

    draw = ImageDraw.Draw(overlay)
    for tile_num in layout:
        row, col = tile_to_grid(tile_num)
        px = grid_x + col * tile_size
        py = grid_y + row * tile_size
        label = str(tile_num)
        draw.text((px + 3, py + 2), label, fill=(255, 255, 255, 200), font=font)

    # --- Merge and save ---
    result = Image.alpha_composite(bg, overlay).convert("RGB")
    result.save(output)
    print(f"Saved → {output}")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate Werblers board image")
    parser.add_argument("--seed",       type=int,   default=None,             help="Random seed")
    parser.add_argument("--reveal",     action="store_true",                  help="Show all tile types")
    parser.add_argument("--no-board",   action="store_true",                  help="Use plain background")
    parser.add_argument("--output",     default="board_out.png",              help="Output file path")
    parser.add_argument("--grid-x",     type=int,   default=None,             help="Grid left edge (px)")
    parser.add_argument("--grid-y",     type=int,   default=None,             help="Grid top edge (px)")
    parser.add_argument("--grid-w",     type=int,   default=None,             help="Grid total width (px)")
    parser.add_argument("--grid-h",     type=int,   default=None,             help="Grid total height (px)")
    parser.add_argument("--padding",    type=int,   default=50,               help="Edge padding when auto-sizing (default 50)")
    parser.add_argument("--tile-alpha", type=int,   default=220,              help="Tile opacity 0–255 (default 220)")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randint(0, 9999)

    build_board_image(
        seed=seed,
        reveal=args.reveal,
        use_board_bg=not args.no_board,
        grid_x=args.grid_x,
        grid_y=args.grid_y,
        grid_w=args.grid_w,
        grid_h=args.grid_h,
        padding=args.padding,
        tile_alpha=args.tile_alpha,
        output=args.output,
    )


if __name__ == "__main__":
    main()

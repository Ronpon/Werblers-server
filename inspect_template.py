from PIL import Image
import numpy as np

t = Image.open("Images/Items/Head Armour/Head Armour Finished Cards/Equip card Template.png")
t_rgba = t.convert("RGBA")
w, h = t_rgba.size
print(f"Template size: {w}x{h}, mode: {t.mode}")

arr = np.array(t_rgba)
alpha = arr[:, :, 3]
transparent = alpha < 10

rows = np.any(transparent, axis=1)
cols = np.any(transparent, axis=0)

row_indices = np.where(rows)[0]
col_indices = np.where(cols)[0]

if len(row_indices):
    print(f"Transparent rows: {row_indices[0]} to {row_indices[-1]}")
else:
    print("No transparent rows")

if len(col_indices):
    print(f"Transparent cols: {col_indices[0]} to {col_indices[-1]}")
else:
    print("No transparent cols")

# Sample pixel colours at key positions for layout clues
print(f"\nSample pixels:")
for y in [30, 80, 130, 180, 300, 500, 700, 900, 1100, 1300]:
    if y < h:
        print(f"  y={y}: {arr[y, w//2]}")

p = Image.open("Images/Items/Head Armour/Head Armour Portraits/Bandana.png")
print(f"\nPortrait size: {p.size}, mode: {p.mode}")

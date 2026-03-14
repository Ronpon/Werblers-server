"""Quick demo: show every leg armour ability firing in a real game."""
from werblers_engine.game import Game
from werblers_engine.player import Player
from werblers_engine.types import EquipSlot, Item
from werblers_engine.encounters import _offer_item

def leg(name, bonus, eid=""):
    return Item(name, EquipSlot.LEGS, strength_bonus=bonus, effect_id=eid)

SEP = "-" * 55

# ── Wheelies ──────────────────────────────────────────────
print(SEP)
print("WHEELIES")
g = Game(seed=1)
p = g.player
p.base_strength = 10
p.movement_hand = [3]
r = g.play_turn(0)
print(f"Turn 1 (no last card yet): moved {r.moved_from} → {r.moved_to}")
print(f"  last_card_played = {p.last_card_played}")

p.equip(leg("Wheelies", 2, "wheelies"))
p.movement_hand = [4]
g._decision_counter = 0          # even = Yes
r = g.play_turn(0)
for line in r.encounter_log:
    print(" ", line)

# ── Hermes' Shoes ─────────────────────────────────────────
print(SEP)
print("HERMES' SHOES  (card 1 → treated as 4)")
g2 = Game(seed=1)
p2 = g2.player
p2.base_strength = 10
p2.equip(leg("Hermes' Shoes", 5, "hermes_shoes"))
p2.movement_hand = [1]
g2._decision_counter = 0         # Yes
r2 = g2.play_turn(0)
for line in r2.encounter_log:
    print(" ", line)

# ── Boots of Agility ──────────────────────────────────────
print(SEP)
print("BOOTS OF AGILITY  (+1 movement)")
g3 = Game(seed=1)
p3 = g3.player
p3.base_strength = 10
p3.equip(leg("Boots of Agility", 1, "boots_of_agility"))
p3.movement_hand = [3]
g3._decision_counter = 0         # Yes
r3 = g3.play_turn(0)
for line in r3.encounter_log:
    print(" ", line)

# ── Boots of Streaking ────────────────────────────────────
print(SEP)
print("BOOTS OF STREAKING  (naked = +20 total)")
p4 = Player(base_strength=1)
p4.equip(leg("Boots of Streaking", 7, "boots_of_streaking"))
print(f"  Naked strength:       {p4.total_strength}   (expect 21 = 1+7+13)")
p4.equip(Item("Iron Helm", EquipSlot.HELMET, strength_bonus=2))
print(f"  With helmet equipped: {p4.total_strength}   (expect 10 = 1+7+2, no bonus)")

# ── Boots of Rooting ──────────────────────────────────────
print(SEP)
print("BOOTS OF ROOTING  (position-curse immunity flag)")
p5 = Player()
print(f"  Without boots: is_rooting_immune = {p5.is_rooting_immune}")
p5.equip(leg("Boots of Rooting", 5, "boots_of_rooting"))
print(f"  With boots:    is_rooting_immune = {p5.is_rooting_immune}")

# ── Pack system ───────────────────────────────────────────
print(SEP)
print("PACK SYSTEM  (equip 1st, pack 2nd, displace 3rd)")
p6 = Player(base_strength=5)
items = [
    leg("Flip Flops",   1),
    leg("Sandals",      1),
    leg("Rubber Boots", 2),
]
log = []
# decision sequence: equip?, equip?, pack? (slot full → move current to pack?)
decisions = iter([
    True,          # item 0: equip directly → success
    False,         # item 1: add to pack
    True,          # item 2: equip directly? yes → slot full → move current to pack? yes
    True,
])
decide = lambda prompt, lg: next(decisions)

for item in items:
    _offer_item(p6, item, log, decide)

print(f"  Legs equipped: {[i.name for i in p6.leg_armor]}")
print(f"  Pack:          {[i.name for i in p6.pack]}")
for line in log:
    print(" ", line)

print(SEP)
print("All abilities demonstrated successfully.")

# WERBLERS — VISION DOCUMENT

## Core Concept

Werblers is a turn-based RPG board game played on a 10 (horizontal) x 9 (vertical) grid, totaling 90 tiles.

Players progress across three increasingly dark and dangerous levels of the board in order to defeat the final boss, The Werbler.

The game can be played either:
- Competitively (a race to defeat The Werbler), or
- Cooperatively (players work together to complete a campaign).

The initial build focuses on the **rules engine only** (no UI).

---

# BOARD STRUCTURE

- The board is a 10x9 grid (90 total tiles).
- Tiles are numbered 1–90 for gameplay purposes.
- Movement in the first engine version is treated as linear progression from tile 1 to tile 90.
- Tiles are hidden until revealed.
- Once revealed, a tile’s type remains visible for the rest of the game.

Progression landmarks:
- Tile 30 → Miniboss 1
- Tile 60 → Miniboss 2
- Tile 90 → The Werbler

The board is divided into three levels:

- Level 1: Tiles 1–30
- Level 2: Tiles 31–60
- Level 3: Tiles 61–90

Each level increases in difficulty and power scaling.

---

# OBJECTIVE

Players aim to:

1. Gain strength through equipment and traits.
2. Defeat minibosses at tiles 30 and 60 to progress.
3. Defeat The Werbler at tile 90 to win.

In competitive mode:
- The first player to defeat The Werbler wins.

In cooperative mode:
- All players win once The Werbler is defeated.

---

# HEROES

- Each player selects a unique hero.
- Heroes have special abilities that may modify:
  - Inventory limits
  - Shop behavior
  - Card draw limits
  - Other mechanics
- Starting strength is TBD.
- Example hero ability:
  - May choose 2 items from shops instead of 1.

Hero abilities are not implemented in the first prototype.

---

# TURN STRUCTURE

Each turn:

1. Player draws movement cards until reaching maximum hand size (default: 3).
2. Movement cards are numbered 1–5.
3. Player plays one card to move forward that many tiles.
4. The tile landed on is revealed (if not already revealed).
5. The encounter on that tile is resolved.

Movement is forward only in the initial engine version.

---

# TILE TYPES

Tiles may be:

## Chest
- Player draws an item from the level-appropriate item pool.
- Chest remains usable on future visits.

## Monster
- Player fights a monster from the level-appropriate monster pool.
- Strength is compared.
- Winner gains a Trait.
- Loser gains a Curse.
- Ties grant nothing.

## Item Shop
- Player may trade a Trait for 1 of 3 drawn items.
- Remaining items are discarded (or returned to pool, depending on final deck rules).

## Blank
- No effect.

## Day/Night
- Toggles time of day.
- During Night:
  - All non-blank tiles behave as Monster tiles.
  - Tile types do not permanently change.

## Miniboss
- Fixed at tiles 30 and 60.
- Must be defeated to continue progression.

## Werbler
- Fixed at tile 90.
- Final boss of the game.

---

# INVENTORY SYSTEM

Players may equip:

- 1 Helmet
- 1 Chest piece
- 1 Leg armor
- 2 Hands worth of weapons

Inventory limits may be modified later by heroes, traits, or curses.

Consumables:
- Can be used during combat.
- No slot limits.

---

# COMBAT

Combat is simple strength comparison.

Player Strength =
- Base Strength
- Equipped Items
- Trait bonuses
- Consumables (if used)

Monster Strength =
- Monster’s strength value

If Player Strength > Monster Strength:
- Player wins and gains a Trait.

If Player Strength < Monster Strength:
- Player loses and gains a Curse.

If tied:
- No Trait or Curse awarded.

Combat is intentionally simple and arithmetic-based.

---

# MINIBOSSES

- Located at tiles 30 and 60.
- Stronger than standard monsters.
- Must be defeated to progress beyond that tile.
- If player loses:
  - Player remains on that tile.
  - May retry next turn.

---

# THE WERBLER

- Located at tile 90.
- Final boss encounter.
- If defeated:
  - Player wins (competitive mode).
  - All players win (co-op mode).

- If player loses:
  - Player is sent back to tile 61 (start of Level 3).

---

# COOPERATIVE MODE (FUTURE)

- Players may occupy the same tile.
- Players may trade equipment when on the same tile.
- No stacking limits.

Co-op mode is not implemented in the first engine prototype.

---

# DESIGN PRINCIPLES

- Rules engine first, UI later.
- Clear, debuggable logic.
- Minimal randomness outside card draws.
- Data-driven content (items, monsters, traits defined separately).
- Avoid over-engineering.
- Build in small, testable increments.

---

# OPEN DESIGN QUESTIONS

- Exact starting strength.
- Scaling rules for each level.
- Whether decks are finite or infinite.
- Whether monster pools reshuffle.
- Whether Night modifies difficulty scaling.
- Whether shops require having a Trait to enter.
- Whether future versions use true 2D movement.
- Exact consumable timing rules.

These questions will be resolved before implementation of related systems.
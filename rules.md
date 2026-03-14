# WERBLERS — RULES SPEC (ENGINE v0.1)

This document defines the precise rules required for the first playable prototype.
No UI.
Single-player only.
Linear progression.
Tiles are numbered 1–90.

---

# 1. BOARD STRUCTURE

- The board contains 90 tiles.
- The board is conceptually a 10 (horizontal) x 9 (vertical) grid.
- For v0.1, movement is treated as linear progression from tile 1 to tile 90.
- Player starts at tile 1.
- Tile 30 contains Miniboss 1.
- Tile 60 contains Miniboss 2.
- Tile 90 contains The Werbler.
- Each tile has a hidden type until revealed (exception: DayNight tiles are always visible).

Tile types:
- Chest
- Monster
- Shop
- Blank
- DayNight
- Miniboss (fixed at tiles 30 and 60)
- Werbler (fixed at tile 90)

Tile distribution (excluding fixed tiles at 30, 60, 90 — 87 tiles total):
- Monster: 16
- Chest: 28
- Shop: 13
- Blank: 21
- DayNight: 9 (exactly one per row of 10 tiles)

Tile positions are randomized each game (DayNight tiles placed one per row).

---

# 2. LEVELS

Level 1: tiles 1–30  
Level 2: tiles 31–60  
Level 3: tiles 61–90  

Level determines:
- Monster strength range
- Item strength range

Exact strength values are defined in content data (placeholder values used until real content is provided).

Content pools are finite decks per level:
- Level 1 content: tiles 1–29 (tile 30 is Miniboss 1)
- Level 2 content: tiles 31–59 (tile 60 is Miniboss 2)
- Level 3 content: tiles 61–89 (tile 90 is The Werbler)

---

# 3. PLAYER

Player has:

- position (integer 1–90)
- base_strength (default: 1)
- inventory:
  - helmet (0 or 1)
  - chest (0 or 1)
  - legs (0 or 1)
  - weapons (max 2 hands)
- traits (list)
- curses (list)
- movement_hand (list of cards)
- max_hand_size (default: 3)

---

# 4. MOVEMENT

- Movement deck contains cards numbered 1–5.
- Cards are drawn from a finite deck. Deck contents TBD (placeholder for v0.1).
- When the movement deck is empty, all discarded movement cards are reshuffled to form a new deck.
- At start of turn:
  - Player draws until hand size equals max_hand_size.
- Player chooses one card to play.
- Position increases by the card value.
- Position is truncated: cannot exceed tile 90, and cannot pass a miniboss tile (30, 60) that has not been defeated.
- Played card is discarded.

Backward movement is not allowed.

---

# 5. TILE REVEAL

- When landing on a tile:
  - If hidden, reveal tile type.
- Revealed tiles remain revealed permanently.

---

# 6. DAY/NIGHT SYSTEM

Game state includes:
- is_night (boolean, starts as False — game begins in daytime)

Landing on a DayNight tile:
- Toggle is_night.

DayNight tiles are always visible (never hidden).

If is_night == True:
- ALL tiles (including Blank) behave as Monster tiles, except Miniboss, Werbler, and DayNight tiles which behave normally.
- Tile type remains unchanged internally.
- Encounter behavior is temporarily overridden.
- Fog of war: all previously revealed tiles (except DayNight, Miniboss, and Werbler) revert to hidden state.
- When day returns, previously revealed tiles become visible again with their original types.

If is_night == False:
- Tiles behave normally.
- Previously revealed tiles are visible again.

DayNight, Miniboss, and Werbler tiles are always visible regardless of day/night state.

---

# 7. ENCOUNTERS

## 7.1 Chest
- Player draws one item from level-appropriate item pool.
- If slot available, auto-equip.
- If slot full, item is discarded.
- Chest remains usable on future visits.

## 7.2 Monster
- Draw monster from level-appropriate pool.
- Resolve combat.

## 7.3 Shop
- Player must have at least one Trait to use shop.
- Draw 3 items from level-appropriate pool.
- Player selects 1 item.
- Selected Trait is discarded.
- Remaining items are discarded.

## 7.4 Blank
- No effect.

## 7.5 Miniboss (tiles 30 and 60)
- Acts as a Monster with higher strength.
- Must be defeated to progress beyond that tile.
- If player loses:
  - Player remains on the miniboss tile.
  - Player may retry next turn.
- Once defeated, the miniboss tile has no encounter on future visits.

## 7.6 Werbler (tile 90)
- Final boss encounter.
- If defeated → game is won.
- If lost:
  - Player position is set to tile 61 (start of Level 3).
  - No encounter is triggered on tile 61 when sent back.

---

# 8. COMBAT

Player Strength =
- base_strength
- equipped item bonuses
- trait bonuses
- consumables (if used — consumable content TBD, skeleton in place)

Monster Strength =
- monster strength value

Combat Resolution:

If player_strength > monster_strength:
  - Player wins.
  - Gain 1 Trait.

If player_strength < monster_strength:
  - Player loses.
  - Gain 1 Curse.

If equal:
  - No gain.

Traits and Curses in v0.1 are modifier objects that can affect:
- Player strength (additive bonus/penalty)
- Inventory slot limits (helmet, chest, legs, weapon hand count)
- Max hand size (number of movement cards)
- Movement bonuses (flat bonus per card played, or card value overrides)

For v0.1, placeholder traits/curses with simple strength modifiers are used.

---

# 9. WIN CONDITION

Game ends when:
- Player defeats The Werbler at tile 90.

---

# 10. OUT OF SCOPE (FOR NOW)

- True 2D adjacency movement
- Co-op mode
- Competitive mode
- Trading
- Hero abilities / hero selection
- Backward movement
- Advanced consumable timing
- Deck exhaustion mechanics (finite decks exist but no reshuffle rules yet)
- Advanced trait/curses behavior beyond stat modifiers
- Consumables (structure exists but no content yet)
- UI
- Save/Load
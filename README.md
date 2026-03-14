# Werblers — Turn-Based RPG Board Game Engine (v0.1)

A minimal rules engine for a 90-tile (10×9) linear RPG board game.
No UI — engine only.

## Project structure

```
werblers_engine/          # Core engine package
  __init__.py
  types.py                # Enums, dataclasses (Tile, Item, Monster, Trait, Curse, …)
  board.py                # Board generation, tile distribution, level lookup
  player.py               # Player state, inventory, strength calculation
  combat.py               # Combat resolution (strength comparison)
  deck.py                 # Finite deck manager (shuffle, draw)
  encounters.py           # Encounter handlers for each tile type
  content.py              # Placeholder content pools (monsters, items, traits, curses)
  game.py                 # Game orchestrator — ties everything together

examples/
  example_simulation.py   # Headless demo — runs turns and prints state

tests/
  test_board.py           # Board generation & tile properties
  test_combat.py          # Combat resolution
  test_movement.py        # Movement, truncation, turn flow
```

## Quick start

```bash
# Install test dependency
pip install -r requirements.txt

# Run example simulation
python examples/example_simulation.py

# Run tests
pytest tests/ -v
```

## Design documents

| File | Purpose |
|------|---------|
| `VISION.md` | High-level game vision and design goals |
| `RULES.md` | Precise rules spec for engine v0.1 |
| `PROJECT_INSTRUCTIONS.md` | Rules for AI-assisted development |

## Assumptions Made

1. **Tile distribution**: Monster tiles are assigned ~30% probability; Chest, Shop, Blank, and DayNight each get ~17.5% of remaining non-fixed tiles.  This is a weighted random distribution, not exact counts.  *Justification*: RULES.md specifies "roughly 30%" without exact counts.
2. **Movement deck**: Placeholder deck of 12 cards `[1,1,2,2,2,3,3,3,4,4,5,5]`.  *Justification*: real deck will be provided later; this gives a playable spread.
3. **Content pools**: All monsters, items, traits, and curses use placeholder names/values.  *Justification*: real content will be provided later per user instruction.
4. **Shop item selection**: In headless mode, the first available item is auto-selected.  *Justification*: no player input mechanism in v0.1.
5. **Trait traded in shop**: Oldest trait in the list is discarded.  *Justification*: RULES.md does not specify which trait is traded; oldest is deterministic and simple.
6. **Miniboss tile encounter on re-visit after defeat**: Not triggered again.  Currently miniboss encounter always fires when landing on tile 30/60; if already defeated, the code marks progress and moves on.  *Justification*: RULES.md says "must be defeated to progress" — once defeated, the tile should no longer block.

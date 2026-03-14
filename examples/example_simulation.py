"""Headless example — runs a few turns and prints state.

Usage:
    python -m examples.example_simulation
    — or —
    python examples/example_simulation.py
"""

import sys, os

# Ensure the engine package is importable when running from repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from werblers_engine.game import Game
from werblers_engine.types import GameStatus


def main() -> None:
    game = Game(seed=42)
    print("=== Werblers v0.1 — Example Simulation ===\n")
    print(game.player_summary())
    print()

    max_turns = 30  # safety cap

    for turn in range(1, max_turns + 1):
        # Always play the first card in hand for simplicity.
        result = game.play_turn(card_index=0, shop_choice=0)

        print(f"--- Turn {result.turn_number} ---")
        for line in result.encounter_log:
            print(f"  {line}")
        print()

        if result.game_status != GameStatus.IN_PROGRESS:
            break

    print("=== Final State ===")
    print(game.player_summary())


if __name__ == "__main__":
    main()

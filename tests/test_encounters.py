"""Tests for encounter edge cases, night system, and consumable skeleton."""

from werblers_engine.game import Game
from werblers_engine.types import (
    CombatResult,
    Consumable,
    GameStatus,
    TileType,
)


# ------------------------------------------------------------------
# Miniboss re-encounter
# ------------------------------------------------------------------

def test_miniboss_no_encounter_after_defeat():
    """Once a miniboss is defeated, landing on its tile does nothing."""
    game = Game(seed=10)
    game.player.position = 29
    game.player.base_strength = 100  # guarantee win
    game.player.movement_hand = [1]

    # First visit — fight and win
    result = game.play_turn(card_index=0)
    assert result.moved_to == 30
    assert game.player.miniboss1_defeated is True

    # Move away, then come back
    game.player.position = 29
    game.player.movement_hand = [1]
    result2 = game.play_turn(card_index=0)
    assert result2.moved_to == 30
    assert result2.combat_result is None  # no combat
    assert any("already defeated" in line.lower() for line in result2.encounter_log)


# ------------------------------------------------------------------
# Werbler loss — reset to 61, no encounter
# ------------------------------------------------------------------

def test_werbler_loss_resets_to_61():
    game = Game(seed=10)
    game.player.position = 89
    game.player.base_strength = 1  # too weak
    game.player.movement_hand = [1]
    game.player.miniboss1_defeated = True
    game.player.miniboss2_defeated = True
    result = game.play_turn(card_index=0)
    assert result.moved_to == 90
    assert result.combat_result == CombatResult.LOSE
    assert game.player.position == 61
    assert result.game_status == GameStatus.IN_PROGRESS


def test_werbler_loss_no_encounter_on_61():
    """After being sent back to 61, no encounter fires on that tile."""
    game = Game(seed=10)
    game.player.position = 89
    game.player.base_strength = 1
    game.player.movement_hand = [1]
    game.player.miniboss1_defeated = True
    game.player.miniboss2_defeated = True
    result = game.play_turn(card_index=0)

    # The turn result's encounter log should NOT contain a second encounter
    # after the Werbler loss.  The reset is part of the Werbler encounter.
    encounter_types = [
        line for line in result.encounter_log
        if "tile 61" in line.lower() and "encounter" in line.lower()
    ]
    assert len(encounter_types) == 0


# ------------------------------------------------------------------
# Movement truncation at 90 after Werbler loss
# ------------------------------------------------------------------

def test_movement_truncated_at_90_after_werbler_loss():
    game = Game(seed=10)
    game.player.position = 89
    game.player.base_strength = 1  # lose to Werbler
    game.player.movement_hand = [1]
    game.player.miniboss1_defeated = True
    game.player.miniboss2_defeated = True
    game.play_turn(card_index=0)  # lose, sent to 61

    assert game.player.position == 61

    # Now try to overshoot tile 90 from somewhere close
    game.player.position = 88
    game.player.movement_hand = [5]
    result = game.play_turn(card_index=0)
    assert result.moved_to == 90  # truncated


# ------------------------------------------------------------------
# Night: Blank tiles become Monster encounters
# ------------------------------------------------------------------

def test_night_blank_becomes_monster():
    """At night, Blank tiles should trigger Monster encounters."""
    game = Game(seed=42)
    game.is_night = True

    # Find a Blank tile
    blank_tile = None
    for tile in game.board[1:]:
        if tile.tile_type == TileType.BLANK:
            blank_tile = tile
            break
    assert blank_tile is not None, "Board should have Blank tiles"

    # Position player just before the blank tile
    game.player.position = blank_tile.index - 1
    game.player.movement_hand = [1]
    result = game.play_turn(card_index=0)

    assert result.moved_to == blank_tile.index
    # Should contain Night override message
    assert any("night override" in line.lower() for line in result.encounter_log)


def test_day_blank_no_encounter():
    """During day, Blank tiles should have no encounter."""
    game = Game(seed=42)
    game.is_night = False

    blank_tile = None
    for tile in game.board[1:]:
        if tile.tile_type == TileType.BLANK:
            blank_tile = tile
            break
    assert blank_tile is not None

    game.player.position = blank_tile.index - 1
    game.player.movement_hand = [1]
    result = game.play_turn(card_index=0)
    assert any("nothing happens" in line.lower() for line in result.encounter_log)


# ------------------------------------------------------------------
# Fog of war visibility
# ------------------------------------------------------------------

def test_fog_of_war_hides_tiles_at_night():
    game = Game(seed=42)
    # Reveal some tiles manually
    for i in range(1, 10):
        game.board[i].revealed = True

    game.is_night = False
    day_visible = game.visible_tiles()
    revealed_in_day = [t for t in day_visible if t.tile_type not in (
        TileType.DAY_NIGHT, TileType.MINIBOSS, TileType.WERBLER
    )]
    assert len(revealed_in_day) > 0

    game.is_night = True
    night_visible = game.visible_tiles()
    # At night only DayNight/Miniboss/Werbler should be visible
    for tile in night_visible:
        assert tile.tile_type in (TileType.DAY_NIGHT, TileType.MINIBOSS, TileType.WERBLER)


def test_miniboss_visible_at_night():
    game = Game(seed=42)
    game.is_night = True
    visible = game.visible_tiles()
    visible_indices = [t.index for t in visible]
    assert 30 in visible_indices
    assert 60 in visible_indices
    assert 90 in visible_indices  # Werbler too


# ------------------------------------------------------------------
# Consumable skeleton
# ------------------------------------------------------------------

def test_consumable_adds_combat_strength():
    from werblers_engine.player import Player

    player = Player(base_strength=3)
    potion = Consumable("Strength Potion", strength_bonus=5)
    player.consumables.append(potion)

    # Without consuming
    assert player.total_strength == 3
    assert player.combat_strength(use_consumables=False) == 3

    # With consuming
    assert player.combat_strength(use_consumables=True) == 8
    assert len(player.consumables) == 0  # consumed


def test_consumable_one_use_only():
    from werblers_engine.player import Player

    player = Player(base_strength=2)
    player.consumables.append(Consumable("Elixir", strength_bonus=10))

    _ = player.combat_strength(use_consumables=True)
    # Second call should have no bonus — consumables already spent
    assert player.combat_strength(use_consumables=True) == 2

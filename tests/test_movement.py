"""Tests for movement, truncation, and turn flow."""

from werblers_engine.game import Game
from werblers_engine.types import GameStatus, TileType


def test_movement_increases_position():
    game = Game(seed=10)
    game.player.movement_hand = [3]
    result = game.play_turn(card_index=0)
    assert result.moved_to == 1 + 3  # started at 1, moved 3


def test_movement_truncated_at_90():
    game = Game(seed=10)
    game.player.position = 88
    game.player.movement_hand = [5]
    game.player.miniboss1_defeated = True
    game.player.miniboss2_defeated = True
    result = game.play_turn(card_index=0)
    assert result.moved_to == 90


def test_movement_truncated_at_miniboss():
    game = Game(seed=10)
    game.player.position = 28
    game.player.movement_hand = [5]
    result = game.play_turn(card_index=0)
    # Should stop at tile 30 (miniboss 1 not defeated)
    assert result.moved_to == 30


def test_miniboss_blocks_until_defeated():
    game = Game(seed=10)
    game.player.position = 29
    game.player.movement_hand = [1]
    result = game.play_turn(card_index=0)
    assert result.moved_to == 30
    # Player should NOT have advanced past 30 even if they had more cards
    assert game.player.position == 30


def test_tile_reveal():
    game = Game(seed=10)
    tile = game.board[4]
    assert tile.revealed is False or tile.tile_type == TileType.DAY_NIGHT
    game.player.movement_hand = [3]
    game.play_turn(card_index=0)
    # Tile at position 4 should now be revealed
    assert game.board[4].revealed is True


def test_game_over_on_werbler_defeat():
    game = Game(seed=10)
    game.player.position = 89
    game.player.base_strength = 100  # ensure win
    game.player.movement_hand = [1]
    game.player.miniboss1_defeated = True
    game.player.miniboss2_defeated = True
    result = game.play_turn(card_index=0)
    assert result.game_status == GameStatus.WON


def test_no_backward_movement():
    """Cards with value > 0 never decrease position."""
    game = Game(seed=10)
    game.player.position = 10
    game.player.movement_hand = [1]
    result = game.play_turn(card_index=0)
    assert result.moved_to >= 10


def test_movement_deck_reshuffles_when_empty():
    """Movement deck should reshuffle discards and keep providing cards."""
    from werblers_engine.deck import Deck

    deck = Deck([1, 2, 3], seed=5, auto_reshuffle=True)
    drawn: list[int] = []
    for _ in range(9):  # 3x the deck size — forces 2 reshuffles
        card = deck.draw()
        assert card is not None
        drawn.append(card)
    assert len(drawn) == 9
    # All drawn values should be from the original set
    assert set(drawn) <= {1, 2, 3}


def test_movement_deck_never_runs_out_in_game():
    """Player should always be able to draw movement cards."""
    game = Game(seed=42)
    for _ in range(20):
        if game.status != GameStatus.IN_PROGRESS:
            break
        game.play_turn(card_index=0)
    # After 20 turns the player should still have been able to act
    assert game.turn_number >= 12  # more turns than the 12-card deck

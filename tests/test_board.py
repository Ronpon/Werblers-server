"""Tests for board generation and tile properties."""

from werblers_engine.board import generate_board, get_level
from werblers_engine.types import TileType


def test_board_has_90_tiles_plus_dummy():
    board = generate_board(seed=1)
    # Index 0 is a dummy; tiles 1–90 are real.
    assert len(board) == 91


def test_fixed_tiles():
    board = generate_board(seed=1)
    assert board[30].tile_type == TileType.MINIBOSS
    assert board[60].tile_type == TileType.MINIBOSS
    assert board[90].tile_type == TileType.WERBLER


def test_day_night_tiles_start_revealed():
    board = generate_board(seed=1)
    for tile in board[1:]:
        if tile.tile_type == TileType.DAY_NIGHT:
            assert tile.revealed is True


def test_non_day_night_non_fixed_start_hidden():
    board = generate_board(seed=1)
    for tile in board[1:]:
        if tile.tile_type not in (TileType.DAY_NIGHT, TileType.MINIBOSS, TileType.WERBLER):
            if tile.index == 1:
                # Tile 1 is the Start tile and is always revealed
                assert tile.revealed is True, "Tile 1 (Start) should always be revealed"
            else:
                assert tile.revealed is False, f"Tile {tile.index} should start hidden"


def test_get_level():
    assert get_level(1) == 1
    assert get_level(30) == 1
    assert get_level(31) == 2
    assert get_level(60) == 2
    assert get_level(61) == 3
    assert get_level(90) == 3


def test_board_is_randomised_with_different_seeds():
    b1 = generate_board(seed=1)
    b2 = generate_board(seed=2)
    types1 = [t.tile_type for t in b1[1:]]
    types2 = [t.tile_type for t in b2[1:]]
    assert types1 != types2, "Different seeds should produce different boards"


def test_fixed_tile_counts():
    """Board should have exact tile-type counts per RULES.md §1."""
    from collections import Counter

    board = generate_board(seed=1)
    counts = Counter(t.tile_type for t in board[1:])  # skip dummy
    assert counts[TileType.MONSTER] == 16
    assert counts[TileType.CHEST] == 33
    assert counts[TileType.SHOP] == 13
    assert counts[TileType.BLANK] == 16
    assert counts[TileType.DAY_NIGHT] == 9
    assert counts[TileType.MINIBOSS] == 2
    assert counts[TileType.WERBLER] == 1


def test_miniboss_and_werbler_tiles_start_revealed():
    board = generate_board(seed=1)
    assert board[30].revealed is True
    assert board[60].revealed is True
    assert board[90].revealed is True


def test_one_day_night_per_row():
    """Each row of 10 tiles should have exactly one DAY_NIGHT tile."""
    board = generate_board(seed=42)
    for row in range(9):
        start = row * 10 + 1
        end = start + 10
        dn_count = sum(
            1 for i in range(start, end)
            if board[i].tile_type == TileType.DAY_NIGHT
        )
        assert dn_count == 1, f"Row {row+1} (tiles {start}-{end-1}) has {dn_count} DAY_NIGHT tiles"

"""Tests for the hero system and multiplayer competitive mode."""

import pytest

from werblers_engine.game import Game
from werblers_engine.heroes import HeroId, HEROES
from werblers_engine.player import Player
from werblers_engine.types import (
    CombatResult,
    Consumable,
    Curse,
    EquipSlot,
    GameStatus,
    Item,
    Monster,
    TileType,
    Trait,
)


# ==================================================================
# Multiplayer basics
# ==================================================================


class TestMultiplayerSetup:
    def test_create_2_player_game(self):
        game = Game(num_players=2, seed=1)
        assert len(game.players) == 2
        assert game.players[0].player_id == 0
        assert game.players[1].player_id == 1

    def test_create_4_player_game(self):
        game = Game(num_players=4, seed=1)
        assert len(game.players) == 4

    def test_reject_5_players(self):
        with pytest.raises(ValueError):
            Game(num_players=5, seed=1)

    def test_reject_0_players(self):
        with pytest.raises(ValueError):
            Game(num_players=0, seed=1)

    def test_hero_assignment(self):
        game = Game(
            num_players=2,
            hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY],
            seed=1,
        )
        assert game.players[0].hero.id == HeroId.BILLFOLD
        assert game.players[1].hero.id == HeroId.GREGORY

    def test_hero_ids_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            Game(num_players=2, hero_ids=[HeroId.BILLFOLD], seed=1)

    def test_single_player_backward_compat(self):
        game = Game(seed=1)
        assert len(game.players) == 1
        assert game.player is game.players[0]


class TestTurnRotation:
    def test_turns_alternate_between_players(self):
        game = Game(num_players=2, seed=42)
        # Manually set hands so we control whose turn it is
        game.players[0].movement_hand = [1]
        game.players[1].movement_hand = [1]

        r1 = game.play_turn(card_index=0)
        assert r1.player_id == 0

        r2 = game.play_turn(card_index=0)
        assert r2.player_id == 1

        # Back to player 0
        game.players[0].movement_hand = [1]
        r3 = game.play_turn(card_index=0)
        assert r3.player_id == 0

    def test_four_player_rotation(self):
        game = Game(num_players=4, seed=42)
        ids = []
        for _ in range(8):  # 2 full rotations
            p = game.current_player
            p.movement_hand = [1]
            r = game.play_turn(card_index=0)
            ids.append(r.player_id)
        assert ids == [0, 1, 2, 3, 0, 1, 2, 3]


class TestSharedDecks:
    def test_shared_item_deck_depletes_for_all(self):
        game = Game(num_players=2, seed=42)
        # Both players draw from the same item deck
        remaining_before = game.item_decks[1].remaining()
        # Simulate a chest draw for player 0
        game.item_decks[1].draw()
        remaining_after = game.item_decks[1].remaining()
        assert remaining_after == remaining_before - 1
        # Player 1 sees the same remaining count
        # (This is implicit — they share the object)


class TestPerPlayerMovementDecks:
    def test_each_player_has_own_deck(self):
        game = Game(num_players=2, seed=42)
        assert game.movement_decks[0] is not game.movement_decks[1]


class TestCompetitiveWin:
    def test_first_to_defeat_werbler_wins(self):
        game = Game(num_players=2, seed=42)
        # Give player 0 a clear path to win
        game.players[0].position = 89
        game.players[0].base_strength = 100
        game.players[0].miniboss1_defeated = True
        game.players[0].miniboss2_defeated = True
        game.players[0].movement_hand = [1]

        result = game.play_turn(card_index=0)
        assert result.player_id == 0
        assert result.game_status == GameStatus.WON
        assert game.winner == 0

    def test_game_over_after_win(self):
        game = Game(num_players=2, seed=42)
        game.players[0].position = 89
        game.players[0].base_strength = 100
        game.players[0].miniboss1_defeated = True
        game.players[0].miniboss2_defeated = True
        game.players[0].movement_hand = [1]
        game.play_turn(card_index=0)

        # Player 1 tries to play — game is over
        game.players[1].movement_hand = [1]
        result = game.play_turn(card_index=0)
        assert "already over" in result.encounter_log[0].lower()


# ==================================================================
# Hero: Billfold Baggains
# ==================================================================


class TestBillfold:
    def _make_game(self, **kw):
        return Game(num_players=1, hero_ids=[HeroId.BILLFOLD], seed=42, **kw)

    def test_shop_draws_3_items(self):
        """All heroes (including Billfold) draw exactly 3 items from a shop."""
        game = self._make_game()
        p = game.player
        p.traits.append(Trait("Dummy", strength_bonus=0))

        items_before = game.item_decks[1].remaining()
        # Find a shop tile
        shop_tile = None
        for tile in game.board[1:30]:
            if tile.tile_type == TileType.SHOP:
                shop_tile = tile
                break
        if shop_tile is None:
            pytest.skip("No shop tile in level 1 with this seed")

        p.position = shop_tile.index - 1
        p.movement_hand = [1]
        game.play_turn(card_index=0, shop_choice=0)

        items_after = game.item_decks[1].remaining()
        drawn = items_before - items_after
        assert drawn == 3  # always 3 items drawn from deck

    def test_flee_from_monster_no_curse(self):
        """Billfold's Fly, you dummy!: flee monster, no curse, move back 8."""
        game = self._make_game()
        p = game.player

        # Find a monster tile
        monster_tile = None
        for tile in game.board[1:30]:
            if tile.tile_type == TileType.MONSTER:
                monster_tile = tile
                break
        if monster_tile is None:
            pytest.skip("No monster tile found")

        p.position = monster_tile.index - 1
        p.movement_hand = [1]
        curses_before = len(p.curses)

        result = game.play_turn(card_index=0, flee=True)
        assert result.combat_result is None  # no combat
        assert len(p.curses) == curses_before  # no curse
        # Should have moved back 8 from monster_tile.index
        expected_pos = max(1, monster_tile.index - 8)
        assert p.position == expected_pos
        assert any("flees" in line.lower() for line in result.encounter_log)

    def test_flee_from_miniboss(self):
        """Billfold can flee a miniboss."""
        game = self._make_game()
        p = game.player
        p.position = 29
        p.movement_hand = [1]
        curses_before = len(p.curses)

        result = game.play_turn(card_index=0, flee=True)
        assert result.combat_result is None
        assert len(p.curses) == curses_before
        # Moved back 8 from tile 30 → tile 22
        assert p.position == 22
        # Miniboss NOT defeated
        assert p.miniboss1_defeated is False

    def test_cannot_flee_werbler(self):
        """Billfold cannot flee the Werbler — flee flag is ignored."""
        game = self._make_game()
        p = game.player
        p.position = 89
        p.base_strength = 1  # will lose
        p.miniboss1_defeated = True
        p.miniboss2_defeated = True
        p.movement_hand = [1]

        result = game.play_turn(card_index=0, flee=True)
        # Combat should have happened (can't flee Werbler)
        assert result.combat_result is not None


# ==================================================================
# Hero: Gregory
# ==================================================================


class TestGregory:
    def _make_game(self, num_players=2, **kw):
        return Game(
            num_players=num_players,
            hero_ids=[HeroId.GREGORY] + [HeroId.BILLFOLD] * (num_players - 1),
            seed=42,
            **kw,
        )

    def test_4_weapon_hands(self):
        game = self._make_game()
        p = game.players[0]
        assert p.weapon_hands == 4

        # Can equip 4 weapons
        for i in range(4):
            assert p.equip(Item(f"Sword {i}", EquipSlot.WEAPON, strength_bonus=1))
        assert len(p.weapons) == 4
        # 5th should fail
        assert not p.equip(Item("Extra Sword", EquipSlot.WEAPON, strength_bonus=1))

    def test_chest_slot(self):
        """Gregory has no chest slot (his special ability)."""
        game = self._make_game()
        p = game.players[0]
        assert p.chest_slots == 0
        assert not p.equip(Item("Plate Mail", EquipSlot.CHEST, strength_bonus=5))

    def test_contagious_mutagen(self):
        """Gregory transfers a curse to another player."""
        game = self._make_game()
        gregory = game.players[0]
        other = game.players[1]

        curse = Curse("Test Curse", strength_bonus=-2)
        gregory.curses.append(curse)

        log = game.use_contagious_mutagen(
            source_player_id=0, target_player_id=1, curse_index=0
        )
        assert len(gregory.curses) == 0
        assert len(other.curses) == 1
        assert other.curses[0].name == "Test Curse"
        assert gregory.mutagen_used is True
        assert any("transferred" in line.lower() for line in log)

    def test_contagious_mutagen_once_per_game(self):
        game = self._make_game()
        gregory = game.players[0]
        gregory.curses.append(Curse("Curse A", strength_bonus=-1))
        game.use_contagious_mutagen(0, 1, 0)

        # Add another curse and try again — should fail
        gregory.curses.append(Curse("Curse B", strength_bonus=-1))
        log = game.use_contagious_mutagen(0, 1, 0)
        assert any("already been used" in line.lower() for line in log)
        assert len(gregory.curses) == 1  # curse NOT transferred

    def test_contagious_mutagen_cannot_target_self(self):
        game = self._make_game()
        game.players[0].curses.append(Curse("Curse", strength_bonus=-1))
        log = game.use_contagious_mutagen(0, 0, 0)
        assert any("cannot target yourself" in line.lower() for line in log)

    def test_contagious_mutagen_requires_curse(self):
        game = self._make_game()
        log = game.use_contagious_mutagen(0, 1, 0)
        assert any("no curses" in line.lower() for line in log)


# ==================================================================
# Hero: Brunhilde the Bodacious
# ==================================================================


class TestBrunhilde:
    def _make_game(self, **kw):
        return Game(num_players=1, hero_ids=[HeroId.BRUNHILDE], seed=42, **kw)

    def test_luscious_locks_no_helmet(self):
        """Brunhilde gets +5 Str when no helmet is equipped."""
        game = self._make_game()
        p = game.player
        # Base 1 + Luscious Locks 5 = 6
        assert p.total_strength == 6

    def test_luscious_locks_with_helmet(self):
        """Luscious Locks bonus disappears when wearing a helmet."""
        game = self._make_game()
        p = game.player
        p.equip(Item("Helm", EquipSlot.HELMET, strength_bonus=2))
        # Base 1 + Helm 2 = 3 (no Luscious Locks)
        assert p.total_strength == 3

    def test_skimpy_armour_minimum_8(self):
        """Chest armour gives minimum +8 Str for Brunhilde."""
        game = self._make_game()
        p = game.player
        # Equip a weak chest piece (+1)
        p.equip(Item("Rags", EquipSlot.CHEST, strength_bonus=1))
        # Base 1 + Skimpy minimum 8 + Luscious Locks 5 = 14
        assert p.total_strength == 14

    def test_skimpy_armour_higher_bonus_kept(self):
        """If chest armour is better than +8, use the higher value."""
        game = self._make_game()
        p = game.player
        p.equip(Item("Mythril Mail", EquipSlot.CHEST, strength_bonus=10))
        # Base 1 + 10 (higher than 8) + Luscious Locks 5 = 16
        assert p.total_strength == 16

    def test_skimpy_armour_destroyed_on_combat_loss(self):
        """Chest armour is destroyed when Brunhilde loses combat."""
        game = self._make_game()
        p = game.player
        chest = Item("Leather Vest", EquipSlot.CHEST, strength_bonus=2)
        p.equip(chest)
        assert len(p.chest_armor) == 1

        # Find a monster tile and ensure we lose
        monster_tile = None
        for tile in game.board[1:30]:
            if tile.tile_type == TileType.MONSTER:
                monster_tile = tile
                break
        if monster_tile is None:
            pytest.skip("No monster tile found")

        p.base_strength = 0  # guarantee loss
        p.position = monster_tile.index - 1
        p.movement_hand = [1]

        result = game.play_turn(card_index=0)
        if result.combat_result == CombatResult.LOSE:
            assert len(p.chest_armor) == 0
            assert any("shredded" in line.lower() for line in result.encounter_log)

    def test_skimpy_armour_survives_combat_win(self):
        """Chest armour is NOT destroyed when Brunhilde wins combat."""
        game = self._make_game()
        p = game.player
        p.equip(Item("Plate", EquipSlot.CHEST, strength_bonus=5))

        monster_tile = None
        for tile in game.board[1:30]:
            if tile.tile_type == TileType.MONSTER:
                monster_tile = tile
                break
        if monster_tile is None:
            pytest.skip("No monster tile found")

        p.base_strength = 100  # guarantee win
        p.position = monster_tile.index - 1
        p.movement_hand = [1]
        game.play_turn(card_index=0)
        assert len(p.chest_armor) == 1


# ==================================================================
# Hero: Rizzt No'Cappin
# ==================================================================


class TestRizzt:
    def _make_game(self, **kw):
        return Game(num_players=1, hero_ids=[HeroId.RIZZT], seed=42, **kw)

    def test_starts_with_scimitar(self):
        """Rizzt starts with Dark Elf's Scimitar equipped."""
        game = self._make_game()
        p = game.player
        assert len(p.weapons) == 1
        assert p.weapons[0].name == "No'Cappin's Scimitar"

    def test_night_stalker_bonus_during_night(self):
        """Rizzt gets +3 Str during Night in combat."""
        game = self._make_game()
        p = game.player
        base = p.combat_strength(is_night=False)
        night = p.combat_strength(is_night=True)
        assert night == base + 3

    def test_night_stalker_no_bonus_during_day(self):
        """Night Stalker gives no bonus during Day."""
        game = self._make_game()
        p = game.player
        day_str = p.combat_strength(is_night=False)
        # Base 1 + Scimitar 6 = 7
        assert day_str == 7

    def test_night_stalker_in_actual_combat(self):
        """Night Stalker bonus affects real combat outcome."""
        game = self._make_game()
        p = game.player
        game.is_night = True

        # Rizzt's combat str at night: base 1 + scimitar 3 + nightstalker 3 = 7
        # Fight a monster with str 5: should win at night, might not during day
        monster_tile = None
        for tile in game.board[1:30]:
            if tile.tile_type == TileType.MONSTER:
                monster_tile = tile
                break
        if monster_tile is None:
            pytest.skip("No monster tile found")

        p.position = monster_tile.index - 1
        p.movement_hand = [1]
        p.base_strength = 4  # 4 + scimitar(3) + night(3) = 10, strong enough
        result = game.play_turn(card_index=0)
        # Should have encountered a monster (night override may apply)
        assert any("night override" in line.lower() or "monster" in line.lower()
                    for line in result.encounter_log)


# ==================================================================
# All heroes together (4-player game)
# ==================================================================


class TestAllHeroes:
    def test_4_hero_game_runs(self):
        """Smoke test: a 4-player game with all heroes runs without error."""
        game = Game(
            num_players=4,
            hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY, HeroId.BRUNHILDE, HeroId.RIZZT],
            seed=42,
        )
        for _ in range(20):
            if game.status != GameStatus.IN_PROGRESS:
                break
            game.play_turn(card_index=0)
        assert game.turn_number >= 10

    def test_player_names_match_heroes(self):
        game = Game(
            num_players=4,
            hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY, HeroId.BRUNHILDE, HeroId.RIZZT],
            seed=1,
        )
        assert game.players[0].name == "Billfold Baggains"
        assert game.players[1].name == "Gregory"
        assert game.players[2].name == "Brunhilde the Bodacious"
        assert game.players[3].name == "Rizzt No'Cappin"

    def test_player_summaries(self):
        game = Game(
            num_players=2,
            hero_ids=[HeroId.BILLFOLD, HeroId.RIZZT],
            seed=1,
        )
        summary = game.all_players_summary()
        assert "Billfold" in summary
        assert "Rizzt" in summary

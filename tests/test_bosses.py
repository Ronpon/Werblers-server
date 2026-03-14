"""Tests for mini-boss and werbler encounter mechanics."""

from __future__ import annotations

import pytest

from werblers_engine.types import (
    CombatResult,
    Curse,
    EquipSlot,
    GameStatus,
    Item,
    Monster,
    Trait,
)
from werblers_engine.player import Player
from werblers_engine.deck import Deck
from werblers_engine import encounters as enc
from werblers_engine import content as C
from werblers_engine import effects as fx
from werblers_engine.game import Game
from werblers_engine.heroes import HeroId


def _make_player(**kw) -> Player:
    p = Player(**kw)
    return p


def _empty_item_deck() -> Deck[Item]:
    return Deck([], seed=42, auto_reshuffle=False)


def _item_deck_with(*items: Item) -> Deck[Item]:
    return Deck(list(items), seed=None, auto_reshuffle=False)


def _empty_curse_deck() -> Deck[Curse]:
    return Deck([], seed=42, auto_reshuffle=False)


# ===================================================================
# Item tagging tests
# ===================================================================

class TestItemTags:
    def test_gun_items_have_is_gun_and_is_ranged(self):
        gun_names = {
            "Motha-flippin' Machine Gun",
            "Plasma Blaster",
            "Laser Rifle",
            "Alien Rifle",
            "Bugger Blaster",
        }
        all_items = C.ITEM_POOL_L1 + C.ITEM_POOL_L2 + C.ITEM_POOL_L3
        for item in all_items:
            if item.name in gun_names:
                assert item.is_gun, f"{item.name} should be is_gun"
                assert item.is_ranged, f"{item.name} should be is_ranged"

    def test_freeze_ray_is_ranged_but_not_gun(self):
        all_items = C.ITEM_POOL_L2
        fr = next(i for i in all_items if i.name == "Freeze Ray")
        assert fr.is_ranged
        assert not fr.is_gun

    def test_melee_weapons_are_not_ranged(self):
        melee_names = {"Spork", "Rusty Blade", "Pot Lid", "Sweeney's Razor", "Claymore of Freedom"}
        all_items = C.ITEM_POOL_L1 + C.ITEM_POOL_L2 + C.ITEM_POOL_L3
        for item in all_items:
            if item.name in melee_names:
                assert not item.is_ranged, f"{item.name} should not be ranged"
                assert not item.is_gun, f"{item.name} should not be gun"


# ===================================================================
# Boss pool tests
# ===================================================================

class TestBossPools:
    def test_miniboss_t1_pool_has_4(self):
        assert len(C.MINIBOSS_POOL_T1) == 4

    def test_miniboss_t2_pool_has_4(self):
        assert len(C.MINIBOSS_POOL_T2) == 4

    def test_werbler_pool_has_4(self):
        assert len(C.WERBLER_POOL) == 4

    def test_all_minibosses_have_effect_ids(self):
        for m in C.MINIBOSS_POOL_T1 + C.MINIBOSS_POOL_T2:
            assert m.effect_id, f"{m.name} missing effect_id"

    def test_all_werblers_have_effect_ids(self):
        for w in C.WERBLER_POOL:
            assert w.effect_id, f"{w.name} missing effect_id"

    def test_werbler_strengths_are_40(self):
        for w in C.WERBLER_POOL:
            assert w.strength == 40, f"{w.name} should have 40 str"


# ===================================================================
# Game init: boss deck + werbler assignment
# ===================================================================

class TestGameBossInit:
    def test_game_has_miniboss_decks(self):
        g = Game(num_players=2, seed=1,
                 hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY])
        assert g.miniboss_deck_t1 is not None
        assert g.miniboss_deck_t2 is not None

    def test_game_assigns_different_werblers(self):
        g = Game(num_players=4, seed=1,
                 hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY,
                           HeroId.BRUNHILDE, HeroId.RIZZT])
        assigned = set()
        for pid, w in g.player_werblers.items():
            assert w.name not in assigned, f"Duplicate werbler: {w.name}"
            assigned.add(w.name)
        assert len(assigned) == 4

    def test_no_active_miniboss_at_start(self):
        g = Game(num_players=1, seed=1)
        assert g.active_miniboss_t1 is None
        assert g.active_miniboss_t2 is None


# ===================================================================
# Tier 1 mini-boss modifier tests
# ===================================================================

class TestShieldedGolem:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T1 if m.effect_id == "shielded_golem")

    def test_armoured_reduces_per_equipped_item(self):
        p = _make_player(base_strength=20)
        p.helmets.append(Item("Hat", EquipSlot.HELMET, strength_bonus=3))
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=5))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # 2 items, each loses 1 Str → penalty of 2
        assert pm == -2  # net: -2 from ability, no 2H bonus
        assert not aw

    def test_two_handed_weapon_bonus(self):
        p = _make_player(base_strength=20)
        p.weapons.append(Item("BFG", EquipSlot.WEAPON, strength_bonus=10, hands=2))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # 1 item penalty (-1) + 1 two-handed bonus (+5) = +4
        assert pm == 4


class TestFlamingGolem:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T1 if m.effect_id == "flaming_golem")

    def test_head_chest_penalty(self):
        p = _make_player(base_strength=20)
        p.helmets.append(Item("Hat", EquipSlot.HELMET, strength_bonus=5))
        p.chest_armor.append(Item("Vest", EquipSlot.CHEST, strength_bonus=3))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # hat loses min(2,5)=2, vest loses min(2,3)=2 → -4
        assert pm == -4
        assert not aw

    def test_gauntlet_auto_win(self):
        p = _make_player(base_strength=1)
        p.weapons.append(Item("Mage's Gauntlet", EquipSlot.WEAPON, strength_bonus=5))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert aw

    def test_no_gauntlet_no_auto_win(self):
        p = _make_player(base_strength=1)
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=5))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert not aw


class TestGhostlyGolem:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T1 if m.effect_id == "ghostly_golem")

    def test_iron_auto_win(self):
        p = _make_player(base_strength=1)
        p.helmets.append(Item("Iron Helm", EquipSlot.HELMET, strength_bonus=2))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert aw

    def test_no_iron_no_auto_win(self):
        p = _make_player(base_strength=1)
        p.helmets.append(Item("Leather Cap", EquipSlot.HELMET, strength_bonus=3))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert not aw

    def test_run_back_on_loss(self):
        boss = self._boss()
        p = _make_player(base_strength=1)
        p.position = 30
        log: list[str] = []
        result = enc.encounter_miniboss(
            p, boss, _empty_item_deck(), log,
        )
        assert result == CombatResult.LOSE
        # Ghostly Golem sends player back 10 spaces
        assert p.position == 20
        assert any("Run awaaaaaay" in m for m in log)


class TestGoaaaaaaaalem:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T1 if m.effect_id == "goaaaaaaaalem")

    def test_no_free_hands_penalty(self):
        p = _make_player(base_strength=20)
        # Fill both weapon hands
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=5, hands=1))
        p.weapons.append(Item("Axe", EquipSlot.WEAPON, strength_bonus=5, hands=1))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # -5 from no free hands, no leg bonus
        assert pm == -5

    def test_leg_armour_doubled(self):
        p = _make_player(base_strength=20)
        p.leg_armor.append(Item("Boots", EquipSlot.LEGS, strength_bonus=4))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # +4 leg bonus (doubles the 4)
        assert pm == 4

    def test_combined_penalty_and_bonus(self):
        p = _make_player(base_strength=20)
        p.weapons.append(Item("Big Sword", EquipSlot.WEAPON, strength_bonus=10, hands=2))
        p.leg_armor.append(Item("Boots", EquipSlot.LEGS, strength_bonus=3))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # 2H fills both hands → -5; leg bonus +3
        assert pm == -2


# ===================================================================
# Tier 2 mini-boss modifier tests
# ===================================================================

class TestSkyDragon:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T2 if m.effect_id == "sky_dragon")

    def test_non_guns_zeroed(self):
        p = _make_player(base_strength=20)
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=8))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert pm == -8

    def test_guns_get_bonus(self):
        p = _make_player(base_strength=20)
        p.weapons.append(Item("Rifle", EquipSlot.WEAPON, strength_bonus=10, is_gun=True, is_ranged=True))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert pm == 5  # +5 for one gun

    def test_mixed_weapons(self):
        p = _make_player(base_strength=20)
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=6))
        p.weapons.append(Item("Rifle", EquipSlot.WEAPON, strength_bonus=10, is_gun=True, is_ranged=True))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        # -6 from sword, +5 from gun
        assert pm == -1


class TestCrossroadsDemon:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T2 if m.effect_id == "crossroads_demon")

    def test_no_helmet_penalty(self):
        p = _make_player(base_strength=20)
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert pm == -10

    def test_helmet_no_penalty(self):
        p = _make_player(base_strength=20)
        p.helmets.append(Item("Hat", EquipSlot.HELMET, strength_bonus=3))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert pm == 0


class TestTheWatcher:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T2 if m.effect_id == "the_watcher")

    def test_empty_slots_bonus(self):
        p = _make_player(base_strength=20)
        # Default: 1 helmet slot, 1 chest slot, 1 legs slot, 2 weapon hands
        # All empty → 5 empty slots → +10
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert pm == 10  # 5 slots × 2

    def test_fully_equipped_no_bonus(self):
        p = _make_player(base_strength=20)
        p.helmets.append(Item("Hat", EquipSlot.HELMET, strength_bonus=3))
        p.chest_armor.append(Item("Vest", EquipSlot.CHEST, strength_bonus=3))
        p.leg_armor.append(Item("Boots", EquipSlot.LEGS, strength_bonus=3))
        p.weapons.append(Item("Big Sword", EquipSlot.WEAPON, strength_bonus=10, hands=2))
        log: list[str] = []
        pm, mm, aw = enc._apply_miniboss_modifiers(p, self._boss(), log)
        assert pm == 0


class TestOgreCutpurse:
    def _boss(self):
        return next(m for m in C.MINIBOSS_POOL_T2 if m.effect_id == "ogre_cutpurse")

    def test_empty_pack_gives_player_bonus(self):
        p = _make_player(base_strength=30)
        log: list[str] = []
        mm = enc._ogre_pre_combat(p, self._boss(), log)
        # Empty pack → −5 to monster (i.e. +5 player)
        assert mm == -5
        assert any("Empty-Handed" in m for m in log)

    def test_pack_items_discarded_and_str_added(self):
        p = _make_player(base_strength=30)
        p.pack.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=5))
        p.pack.append(Item("Shield", EquipSlot.WEAPON, strength_bonus=3))
        log: list[str] = []
        mm = enc._ogre_pre_combat(p, self._boss(), log)
        assert mm == 8  # 5 + 3 added to monster
        assert len(p.pack) == 0

    def test_consumables_and_monsters_discarded(self):
        from werblers_engine.types import Consumable
        p = _make_player(base_strength=30)
        p.consumables.append(Consumable("Potion", strength_bonus=3))
        p.captured_monsters.append(Monster("Rat", strength=2))
        log: list[str] = []
        mm = enc._ogre_pre_combat(p, self._boss(), log)
        assert mm == 0  # consumables/monsters don't add str to monster
        assert len(p.consumables) == 0
        assert len(p.captured_monsters) == 0


# ===================================================================
# Miniboss encounter integration tests
# ===================================================================

class TestMinibossEncounter:
    def test_strong_player_wins_and_gets_reward(self):
        boss = Monster("Test Boss", strength=5, level=1, effect_id="shielded_golem")
        p = _make_player(base_strength=20)
        reward_item = Item("Prize", EquipSlot.WEAPON, strength_bonus=10)
        deck = _item_deck_with(reward_item)
        log: list[str] = []
        result = enc.encounter_miniboss(p, boss, deck, log)
        assert result == CombatResult.WIN
        assert any("Victory" in m for m in log)
        assert any("Prize" in m for m in log)

    def test_weak_player_loses_and_stays(self):
        boss = Monster("Test Boss", strength=50, level=1, effect_id="shielded_golem")
        p = _make_player(base_strength=1)
        p.position = 30
        log: list[str] = []
        result = enc.encounter_miniboss(p, boss, _empty_item_deck(), log)
        assert result == CombatResult.LOSE
        assert any("Defeat" in m for m in log)

    def test_auto_win_via_iron(self):
        boss = next(m for m in C.MINIBOSS_POOL_T1 if m.effect_id == "ghostly_golem")
        p = _make_player(base_strength=1)
        p.helmets.append(Item("Iron Helm", EquipSlot.HELMET, strength_bonus=2))
        reward_item = Item("Prize", EquipSlot.WEAPON, strength_bonus=10)
        deck = _item_deck_with(reward_item)
        log: list[str] = []
        result = enc.encounter_miniboss(p, boss, deck, log)
        assert result == CombatResult.WIN
        assert any("auto-win" in m.lower() for m in log)

    def test_flee_billfold(self):
        from werblers_engine.heroes import HEROES
        boss = C.MINIBOSS_POOL_T1[0]
        p = _make_player(base_strength=1)
        p.assign_hero(HEROES[HeroId.BILLFOLD])
        log: list[str] = []
        result = enc.encounter_miniboss(p, boss, _empty_item_deck(), log, flee=True)
        assert result is None
        assert any("flees" in m for m in log)


# ===================================================================
# Werbler modifier tests
# ===================================================================

class TestBradyModifiers:
    def _werbler(self):
        return next(w for w in C.WERBLER_POOL if w.effect_id == "brady")

    def test_melee_penalty(self):
        p = _make_player(base_strength=50)
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=8))
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log)
        assert pm == -3

    def test_ranged_no_penalty(self):
        p = _make_player(base_strength=50)
        p.weapons.append(Item("Rifle", EquipSlot.WEAPON, strength_bonus=10, is_ranged=True))
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log)
        assert pm == 0


class TestHarryModifiers:
    def _werbler(self):
        return next(w for w in C.WERBLER_POOL if w.effect_id == "harry")

    def test_day_bonus(self):
        p = _make_player(base_strength=50)
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log, is_night=False)
        assert mm == 10

    def test_night_no_bonus(self):
        p = _make_player(base_strength=50)
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log, is_night=True)
        assert mm == 0


class TestArMegGeddonModifiers:
    def _werbler(self):
        return next(w for w in C.WERBLER_POOL if w.effect_id == "ar_meg_geddon")

    def test_minions_nullified(self):
        from werblers_engine.types import Minion
        p = _make_player(base_strength=50)
        p.minions.append(Minion("Bob", strength_bonus=5))
        fx.refresh_tokens(p)
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log)
        # Minion contributes 5 → penalty of 5
        assert pm == -5


class TestJohnilModifiers:
    def _werbler(self):
        return next(w for w in C.WERBLER_POOL if w.effect_id == "johnil")

    def test_one_handed_penalty(self):
        p = _make_player(base_strength=50)
        p.weapons.append(Item("Dagger", EquipSlot.WEAPON, strength_bonus=5, hands=1))
        p.weapons.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=8, hands=1))
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log)
        assert pm == -8  # 2 one-handed × -4

    def test_two_handed_no_penalty(self):
        p = _make_player(base_strength=50)
        p.weapons.append(Item("BFG", EquipSlot.WEAPON, strength_bonus=10, hands=2))
        log: list[str] = []
        pm, mm = enc._apply_werbler_modifiers(p, self._werbler(), log)
        assert pm == 0


# ===================================================================
# Werbler loss effects
# ===================================================================

class TestBradyLoss:
    def _werbler(self):
        w = next(w for w in C.WERBLER_POOL if w.effect_id == "brady")
        # Reset theft counter for each test
        if hasattr(w, "_brady_thefts"):
            del w._brady_thefts
        return w

    def test_steal_helmet(self):
        w = Monster("Brady", strength=40, level=3, effect_id="brady")
        p = _make_player()
        p.helmets.append(Item("Nice Hat", EquipSlot.HELMET, strength_bonus=5))
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert len(p.helmets) == 0
        assert w.strength == 45
        assert w._brady_thefts == 1

    def test_max_two_thefts(self):
        w = Monster("Brady", strength=40, level=3, effect_id="brady")
        w._brady_thefts = 2
        p = _make_player()
        p.helmets.append(Item("Hat", EquipSlot.HELMET, strength_bonus=3))
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert len(p.helmets) == 1  # not stolen
        assert w.strength == 40  # unchanged

    def test_no_helmet_doesnt_count(self):
        w = Monster("Brady", strength=40, level=3, effect_id="brady")
        p = _make_player()
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert w.strength == 40
        assert getattr(w, "_brady_thefts", 0) == 0


class TestHarryLoss:
    def test_tainted_gives_curse(self):
        w = Monster("Harry", strength=40, level=3, effect_id="harry")
        p = _make_player()
        # Create a L3 monster with a known curse
        m = Monster("Test Monster", strength=25, level=3, curse_name="Stabbed")
        m_deck = Deck([m], seed=None, auto_reshuffle=False)
        c_deck = _empty_curse_deck()
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log, monster_deck_l3=m_deck, curse_deck=c_deck)
        assert len(p.curses) == 1
        assert p.curses[0].name == "Stabbed"

    def test_tainted_no_monster_deck(self):
        w = Monster("Harry", strength=40, level=3, effect_id="harry")
        p = _make_player()
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert len(p.curses) == 0


class TestArMegGeddonLoss:
    def test_discard_chest_and_legs(self):
        w = Monster("Ar-Meg-Geddon", strength=40, level=3, effect_id="ar_meg_geddon")
        p = _make_player()
        p.chest_armor.append(Item("Vest", EquipSlot.CHEST, strength_bonus=3))
        p.leg_armor.append(Item("Boots", EquipSlot.LEGS, strength_bonus=4))
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert len(p.chest_armor) == 0
        assert len(p.leg_armor) == 0
        assert any("Schmegged" in m for m in log)


class TestJohnilLoss:
    def test_lose_all_traits_if_two_or_fewer(self):
        w = Monster("Joh'Neil", strength=40, level=3, effect_id="johnil")
        p = _make_player()
        p.traits.append(Trait("A", strength_bonus=1))
        p.traits.append(Trait("B", strength_bonus=2))
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert len(p.traits) == 0

    def test_lose_two_traits_with_select(self):
        w = Monster("Joh'Neil", strength=40, level=3, effect_id="johnil")
        p = _make_player()
        t1 = Trait("A", strength_bonus=1)
        t2 = Trait("B", strength_bonus=2)
        t3 = Trait("C", strength_bonus=3)
        p.traits.extend([t1, t2, t3])

        # select_fn picks the first N from the list
        def select(items, n, prompt):
            return items[:n]

        log: list[str] = []
        enc._apply_werbler_loss(p, w, log, select_fn=select)
        assert len(p.traits) == 1
        assert p.traits[0].name == "C"

    def test_no_traits_no_effect(self):
        w = Monster("Joh'Neil", strength=40, level=3, effect_id="johnil")
        p = _make_player()
        log: list[str] = []
        enc._apply_werbler_loss(p, w, log)
        assert any("no traits" in m.lower() for m in log)


# ===================================================================
# Werbler encounter integration
# ===================================================================

class TestWerblerEncounter:
    def test_strong_player_wins(self):
        w = Monster("Test Werbler", strength=5, level=3, effect_id="brady")
        p = _make_player(base_strength=50)
        log: list[str] = []
        result, status = enc.encounter_werbler(p, w, _empty_curse_deck(), log)
        assert result == CombatResult.WIN
        assert status == GameStatus.WON

    def test_weak_player_loses_sent_to_61(self):
        w = Monster("Test Werbler", strength=100, level=3, effect_id="harry")
        p = _make_player(base_strength=1)
        p.position = 90
        log: list[str] = []
        result, status = enc.encounter_werbler(p, w, _empty_curse_deck(), log)
        assert result == CombatResult.LOSE
        assert status == GameStatus.IN_PROGRESS
        assert p.position == 61

    def test_kneel_curse_boosts_werbler(self):
        w = Monster("Test Werbler", strength=5, level=3, effect_id="brady")
        p = _make_player(base_strength=50)
        p.curses.append(Curse("KNEEL!", effect_id="kneel"))
        log: list[str] = []
        result, status = enc.encounter_werbler(p, w, _empty_curse_deck(), log)
        assert any("KNEEL" in m for m in log)

    def test_harry_day_bonus(self):
        w = Monster("Harry", strength=5, level=3, effect_id="harry")
        p = _make_player(base_strength=50)
        log: list[str] = []
        # During the day, Harry gets +10 → 15 total; player at 50 still wins
        result, status = enc.encounter_werbler(p, w, _empty_curse_deck(), log, is_night=False)
        assert result == CombatResult.WIN
        assert any("Light it up" in m for m in log)


# ===================================================================
# Game-level miniboss reveal/defeat flow
# ===================================================================

class TestMinibossRevealFlow:
    def test_first_player_reveals_miniboss(self):
        g = Game(num_players=2, seed=42,
                 hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY])
        p = g.players[0]
        p.position = 29
        p.miniboss1_defeated = False
        p.base_strength = 100  # guarantee win
        p.movement_hand = [1]
        g.play_turn(card_index=0)
        # Should have revealed and fought a boss
        assert p.miniboss1_defeated
        assert g.active_miniboss_t1 is None  # cleared after win

    def test_defeated_boss_reveals_new_one(self):
        g = Game(num_players=2, seed=42,
                 hero_ids=[HeroId.BILLFOLD, HeroId.GREGORY])
        # Player 1 defeats first boss
        p1 = g.players[0]
        p1.position = 29
        p1.base_strength = 100
        p1.movement_hand = [1]
        g.play_turn(card_index=0)
        assert p1.miniboss1_defeated
        # Active boss should be cleared (defeated)
        assert g.active_miniboss_t1 is None

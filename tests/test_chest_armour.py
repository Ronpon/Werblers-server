"""Tests for chest armour items and their abilities.

Covers:
- Content pool membership (all real chest items in correct tiers)
- Bionic Arms: +2 weapon hand slots while equipped
- Barbarian Armour: +4 extra Str when a 2H weapon is equipped
- Wizard's Robes: +1 Str per Trait held
- Item.weapon_hand_bonus and Item.hands fields
- can_equip for weapons using hands cost
- Strength contributions to total_strength and combat_strength
- Integration smoke test
"""

import pytest

from werblers_engine.types import EquipSlot, Item, Trait
from werblers_engine.player import Player
from werblers_engine import content as C
from werblers_engine import effects as fx
from werblers_engine.game import Game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chest(name: str, bonus: int, effect_id: str = "", weapon_hand_bonus: int = 0) -> Item:
    return Item(name, EquipSlot.CHEST, strength_bonus=bonus,
                effect_id=effect_id, weapon_hand_bonus=weapon_hand_bonus)


def _weapon(name: str, bonus: int, hands: int = 1) -> Item:
    return Item(name, EquipSlot.WEAPON, strength_bonus=bonus, hands=hands)


def _player(**kwargs) -> Player:
    return Player(**kwargs)


# ---------------------------------------------------------------------------
# Content pool membership
# ---------------------------------------------------------------------------

class TestChestArmourPools:

    def _chests(self, pool: list[Item]) -> set[str]:
        return {i.name for i in pool if i.slot == EquipSlot.CHEST}

    def test_tier1_chests_in_L1_pool(self):
        expected = {
            "Sweater Vest", "Peasant's Robes", "Puffy Shirt",
            "Junk Mail", "Leather Armour", "Fan Mail",
            "Barbarian Armour",
        }
        assert expected <= self._chests(C.ITEM_POOL_L1)

    def test_tier2_chests_in_L2_pool(self):
        expected = {
            "Iron Armour", "3D-Printed Armour", "Steel Plate Armour",
            "Chain Mail", "Bulletproof Vest", "Wizard's Robes",
        }
        assert expected <= self._chests(C.ITEM_POOL_L2)

    def test_tier3_chests_in_L3_pool(self):
        expected = {
            "Padded Doublet of Light",
            "Bionic Arms", "Mithril Chain Vest", "Dragonscale Chestplate",
            "Chestplate Made of What the Black Box is Made of",
        }
        assert expected <= self._chests(C.ITEM_POOL_L3)

    def test_bionic_arms_has_correct_effect_id(self):
        bionic = next(i for i in C.ITEM_POOL_L3 if i.name == "Bionic Arms")
        assert bionic.effect_id == "bionic_arms"
        assert bionic.weapon_hand_bonus == 2

    def test_barbarian_armour_has_correct_effect_id(self):
        barb = next(i for i in C.ITEM_POOL_L1 if i.name == "Barbarian Armour")
        assert barb.effect_id == "barbarian_armour"

    def test_wizards_robes_has_correct_effect_id(self):
        robes = next(i for i in C.ITEM_POOL_L2 if i.name == "Wizard's Robes")
        assert robes.effect_id == "wizards_robes"

    def test_no_placeholder_chest_items_remain(self):
        """Old placeholder names should not be in any pool."""
        all_items = C.ITEM_POOL_L1 + C.ITEM_POOL_L2 + C.ITEM_POOL_L3
        old_names = {"Padded Vest", "Reinforced Vest", "Mythril Mail", "Shadow Plate"}
        actual_names = {i.name for i in all_items}
        assert not old_names & actual_names


# ---------------------------------------------------------------------------
# Item dataclass new fields
# ---------------------------------------------------------------------------

class TestItemFields:

    def test_weapon_hand_bonus_defaults_to_zero(self):
        item = Item("Sword", EquipSlot.WEAPON, strength_bonus=3)
        assert item.weapon_hand_bonus == 0

    def test_hands_defaults_to_one(self):
        item = Item("Sword", EquipSlot.WEAPON, strength_bonus=3)
        assert item.hands == 1

    def test_weapon_hand_bonus_set_explicitly(self):
        item = _chest("Bionic Arms", 1, weapon_hand_bonus=2)
        assert item.weapon_hand_bonus == 2

    def test_hands_set_explicitly(self):
        item = _weapon("Greatsword", 5, hands=2)
        assert item.hands == 2


# ---------------------------------------------------------------------------
# Bionic Arms — extra weapon hand slots
# ---------------------------------------------------------------------------

class TestBionicArms:

    def test_bionic_arms_grants_two_extra_weapon_hands(self):
        p = _player()
        assert p.weapon_hands == 2
        p.equip(_chest("Bionic Arms", 1, "bionic_arms", weapon_hand_bonus=2))
        assert p.weapon_hands == 4

    def test_unequipping_bionic_arms_removes_bonus(self):
        p = _player()
        bionic = _chest("Bionic Arms", 1, "bionic_arms", weapon_hand_bonus=2)
        p.equip(bionic)
        assert p.weapon_hands == 4
        p.unequip(bionic)
        assert p.weapon_hands == 2

    def test_bionic_arms_allows_more_weapons_equipped(self):
        p = _player()
        p.equip(_chest("Bionic Arms", 1, "bionic_arms", weapon_hand_bonus=2))
        assert p.equip(_weapon("Sword A", 3)) is True
        assert p.equip(_weapon("Sword B", 3)) is True
        assert p.equip(_weapon("Sword C", 3)) is True
        assert p.equip(_weapon("Sword D", 3)) is True
        # 5th weapon exceeds 4 hands
        assert p.equip(_weapon("Sword E", 3)) is False

    def test_bionic_arms_strength_bonus_also_counted(self):
        p = _player(base_strength=5)
        p.equip(_chest("Bionic Arms", 1, "bionic_arms", weapon_hand_bonus=2))
        assert p.total_strength == 6  # base 5 + chest 1


# ---------------------------------------------------------------------------
# can_equip — hands-aware weapon slot check
# ---------------------------------------------------------------------------

class TestCanEquipWeapons:

    def test_1h_weapon_uses_one_hand(self):
        p = _player()
        assert p.can_equip(_weapon("Dagger", 1, hands=1)) is True
        p.equip(_weapon("Dagger", 1, hands=1))
        assert p.can_equip(_weapon("Shortsword", 2, hands=1)) is True
        p.equip(_weapon("Shortsword", 2, hands=1))
        # 2 hands used, 2 limit — full
        assert p.can_equip(_weapon("Club", 1, hands=1)) is False

    def test_2h_weapon_uses_two_hands(self):
        p = _player()
        greatsword = _weapon("Greatsword", 5, hands=2)
        assert p.can_equip(greatsword) is True
        p.equip(greatsword)
        # 2 hands used — cannot add any more
        assert p.can_equip(_weapon("Dagger", 1, hands=1)) is False
        assert p.can_equip(_weapon("Axe", 3, hands=2)) is False

    def test_1h_plus_2h_refused_if_over_limit(self):
        p = _player()
        p.equip(_weapon("Dagger", 1, hands=1))  # uses 1 hand
        # 1 hand free — 2H weapon needs 2
        assert p.can_equip(_weapon("Greatsword", 5, hands=2)) is False

    def test_bionic_arms_enables_2h_plus_1h(self):
        p = _player()
        p.equip(_chest("Bionic Arms", 1, "bionic_arms", weapon_hand_bonus=2))
        # 4 hands now
        p.equip(_weapon("Greatsword", 5, hands=2))  # uses 2
        assert p.can_equip(_weapon("Dagger", 1, hands=1)) is True  # 2 left
        assert p.can_equip(_weapon("Sword", 3, hands=2)) is True   # exactly 2 left


# ---------------------------------------------------------------------------
# Barbarian Armour
# ---------------------------------------------------------------------------

class TestBarbarianArmour:

    def _equip_barb(self, p: Player) -> None:
        p.equip(_chest("Barbarian Armour", 3, "barbarian_armour"))

    def test_base_bonus_only_with_no_weapon(self):
        p = _player(base_strength=5)
        self._equip_barb(p)
        assert p.total_strength == 5 + 3  # no 2H weapon → no extra

    def test_base_bonus_only_with_1h_weapon(self):
        p = _player(base_strength=5)
        self._equip_barb(p)
        p.equip(_weapon("Dagger", 1, hands=1))
        assert p.total_strength == 5 + 3 + 1  # still no 2H weapon

    def test_full_bonus_with_2h_weapon(self):
        p = _player(base_strength=5)
        self._equip_barb(p)
        p.equip(_weapon("Greatsword", 4, hands=2))
        # 5 (base) + 3 (barb base) + 4 (barb hook) + 4 (sword) = 16
        assert p.total_strength == 5 + 3 + 4 + 4

    def test_2h_bonus_disappears_when_weapon_unequipped(self):
        p = _player(base_strength=5)
        self._equip_barb(p)
        sword = _weapon("Greatsword", 4, hands=2)
        p.equip(sword)
        assert p.total_strength == 16
        p.unequip(sword)
        assert p.total_strength == 5 + 3  # hook gone

    def test_full_bonus_in_combat_strength(self):
        p = _player(base_strength=5)
        self._equip_barb(p)
        p.equip(_weapon("Greatsword", 4, hands=2))
        assert p.combat_strength() == p.total_strength


# ---------------------------------------------------------------------------
# Wizard's Robes
# ---------------------------------------------------------------------------

class TestWizardsRobes:

    def _equip_robes(self, p: Player) -> None:
        p.equip(_chest("Wizard's Robes", 1, "wizards_robes"))

    def test_no_bonus_with_no_traits(self):
        p = _player(base_strength=5)
        self._equip_robes(p)
        assert p.total_strength == 5 + 1  # base 1 only, hook adds 0

    def test_one_trait_adds_one(self):
        p = _player(base_strength=5)
        self._equip_robes(p)
        p.traits.append(Trait("Quick Feet", strength_bonus=0))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 1 + 1

    def test_three_traits_add_three(self):
        p = _player(base_strength=5)
        self._equip_robes(p)
        for i in range(3):
            p.traits.append(Trait(f"T{i}", strength_bonus=0))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 1 + 3

    def test_trait_flat_bonus_also_stacks(self):
        p = _player(base_strength=5)
        self._equip_robes(p)
        p.traits.append(Trait("Iron Will", strength_bonus=2))
        fx.refresh_tokens(p)
        # 5 + 1 (robes base) + 1 (hook: 1 trait) + 2 (trait bonus) = 9
        assert p.total_strength == 9

    def test_both_wizards_robes_and_crown_of_thorns_stack(self):
        """Wearing both gives double the per-trait bonus."""
        p = _player(base_strength=5)
        self._equip_robes(p)
        p.equip(Item("Crown of Thorns", EquipSlot.HELMET, strength_bonus=1,
                     effect_id="crown_of_thorns"))
        p.traits.append(Trait("T", strength_bonus=0))
        fx.refresh_tokens(p)
        # 5 + 1 (robes) + 1 (robes hook) + 1 (crown) + 1 (crown hook) = 9
        assert p.total_strength == 9

    def test_unequipping_robes_removes_bonus(self):
        p = _player(base_strength=5)
        robes = _chest("Wizard's Robes", 1, "wizards_robes")
        p.equip(robes)
        p.traits.append(Trait("T", strength_bonus=0))
        fx.refresh_tokens(p)
        assert p.total_strength == 7
        p.unequip(robes)
        assert p.total_strength == 5  # no robes, trait has 0 str bonus


# ---------------------------------------------------------------------------
# Chest armour strength contributions
# ---------------------------------------------------------------------------

class TestChestStrengthContributions:

    def test_chest_bonus_in_total_strength(self):
        p = _player(base_strength=3)
        p.equip(_chest("Dragonscale Chestplate", 8))
        assert p.total_strength == 11

    def test_plain_chest_items_counted(self):
        for name, bonus in [("Sweater Vest", 1), ("Iron Armour", 4), ("Mithril Chain Vest", 8)]:
            p = _player(base_strength=0)
            p.equip(_chest(name, bonus))
            assert p.total_strength == bonus

    def test_chest_in_combat_strength(self):
        p = _player(base_strength=5)
        p.equip(_chest("Steel Plate Armour", 6))
        assert p.combat_strength() == 11


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestChestArmourIntegration:

    def test_game_turn_with_chest_equipped(self):
        g = Game(seed=22)
        p = g.player
        p.equip(_chest("Iron Armour", 4))
        p.movement_hand = [2]
        result = g.play_turn(card_index=0)
        assert result.moved_to >= result.moved_from

    def test_bionic_arms_in_game_allows_extra_weapons(self):
        g = Game(seed=22)
        p = g.player
        p.equip(_chest("Bionic Arms", 1, "bionic_arms", weapon_hand_bonus=2))
        assert p.weapon_hands == 4
        assert p.equip(_weapon("Sword A", 3)) is True
        assert p.equip(_weapon("Sword B", 3)) is True
        assert p.equip(_weapon("Sword C", 3)) is True

    def test_wizards_robes_updates_dynamically_when_trait_gained(self):
        """Adding a trait after equipping robes immediately changes total_strength."""
        p = _player(base_strength=5)
        p.equip(_chest("Wizard's Robes", 1, "wizards_robes"))
        assert p.total_strength == 6
        p.traits.append(Trait("Clever", strength_bonus=0))
        fx.refresh_tokens(p)
        assert p.total_strength == 7
        p.traits.append(Trait("Wise", strength_bonus=0))
        fx.refresh_tokens(p)
        assert p.total_strength == 8

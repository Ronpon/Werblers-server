"""Tests for head armour (helmet) items and their abilities.

Covers:
- Content pool membership (helmet items in correct level tiers)
- Crown of Thorns (+1 Str per Trait held)
- Helmet slot mechanics: equip, slot limit, extra slot via trait, unequip
- Pack system with helmets
- Strength contribution from helmets
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

def _helm(name: str, bonus: int, effect_id: str = "") -> Item:
    return Item(name, EquipSlot.HELMET, strength_bonus=bonus, effect_id=effect_id)


def _player(**kwargs) -> Player:
    return Player(**kwargs)


# ---------------------------------------------------------------------------
# Content pool membership
# ---------------------------------------------------------------------------

class TestHeadArmourPools:

    def _helmets(self, pool: list[Item]) -> set[str]:
        return {i.name for i in pool if i.slot == EquipSlot.HELMET}

    def test_tier1_helmets_in_L1_pool(self):
        expected = {
            "Colander", "Propeller Hat", "Sweet bandana",
            "Miner\u2019s Helmet", "Baseball Cap", "Lupine Helm",
            "Paper Bag", "Squire\u2019s Helm",
            "Swiss Guard Helmet",
        }
        assert expected <= self._helmets(C.ITEM_POOL_L1)
        # Football Helmet is Tier 2
        assert "Football Helmet" not in self._helmets(C.ITEM_POOL_L1), "Football Helmet should not be in L1 pool"
        # Crown of Thorns and Face Mask have moved to Tier 3
        for name in ("Crown of Thorns", "Face Mask"):
            assert name not in self._helmets(C.ITEM_POOL_L1), f"{name} should not be in L1 pool"

    def test_high_bonus_helmets_in_L3_pool(self):
        """High-strength helmets (+6/+7) and special ability helms belong in Tier 3."""
        expected = {
            "Crown of the Colossus", "Astronaut Helmet",
            "Horned Helm", "Knight's Helm",
            "Crown of Thorns", "Face Mask",
        }
        assert expected <= self._helmets(C.ITEM_POOL_L3)

    def test_high_bonus_helmets_not_in_L1_or_L2_pool(self):
        l1_names = self._helmets(C.ITEM_POOL_L1)
        l2_names = self._helmets(C.ITEM_POOL_L2)
        for name in ("Crown of the Colossus", "Astronaut Helmet", "Horned Helm",
                     "Knight's Helm", "Crown of Thorns", "Face Mask"):
            assert name not in l1_names, f"{name} should not be in L1 pool"
            assert name not in l2_names, f"{name} should not be in L2 pool"

    def test_tier2_helmets_in_L2_pool(self):
        expected = {"Iron Helm", "War Helm"}
        assert expected <= self._helmets(C.ITEM_POOL_L2)

    def test_tier3_helmets_in_L3_pool(self):
        expected = {
            "Crown of the Colossus", "Astronaut Helmet",
            "Horned Helm", "Knight's Helm",
            "Crown of Thorns", "Face Mask",
        }
        assert expected <= self._helmets(C.ITEM_POOL_L3)

    def test_crown_of_thorns_has_effect_id(self):
        all_helms = C.ITEM_POOL_L1 + C.ITEM_POOL_L2 + C.ITEM_POOL_L3
        crown = next((i for i in all_helms if i.name == "Crown of Thorns"), None)
        assert crown is not None
        assert crown.effect_id == "crown_of_thorns"

    def test_all_helmets_have_correct_slot(self):
        for pool in (C.ITEM_POOL_L1, C.ITEM_POOL_L2, C.ITEM_POOL_L3):
            for item in pool:
                if item.slot == EquipSlot.HELMET:
                    assert item.strength_bonus >= 0


# ---------------------------------------------------------------------------
# Crown of Thorns
# ---------------------------------------------------------------------------

class TestCrownOfThorns:

    def _equip_crown(self, p: Player) -> None:
        p.equip(_helm("Crown of Thorns", 1, "crown_of_thorns"))

    def test_no_bonus_with_no_traits(self):
        """Base +1 only when player has no traits."""
        p = _player(base_strength=5)
        self._equip_crown(p)
        assert p.total_strength == 5 + 1  # base + item.strength_bonus, hook adds 0

    def test_one_trait_adds_one(self):
        p = _player(base_strength=5)
        self._equip_crown(p)
        p.traits.append(Trait("Strong Arm", strength_bonus=0))
        fx.refresh_tokens(p)
        # Crown: +1 (base) + 1 (hook) = +2 from item; trait itself has no strength_bonus
        assert p.total_strength == 5 + 1 + 1

    def test_three_traits_add_three(self):
        p = _player(base_strength=5)
        self._equip_crown(p)
        for i in range(3):
            p.traits.append(Trait(f"Trait{i}", strength_bonus=0))
        fx.refresh_tokens(p)
        # Crown: +1 + 3 = +4 from item
        assert p.total_strength == 5 + 1 + 3

    def test_trait_flat_bonus_also_stacks(self):
        """Trait strength_bonus and Crown of Thorns hook both apply."""
        p = _player(base_strength=5)
        self._equip_crown(p)
        p.traits.append(Trait("Iron Will", strength_bonus=2))
        fx.refresh_tokens(p)
        # strength: 5 (base) + 1 (crown base) + 1 (crown hook, 1 trait) + 2 (trait bonus)
        assert p.total_strength == 5 + 1 + 1 + 2

    def test_unequipping_crown_removes_bonus(self):
        p = _player(base_strength=5)
        crown = _helm("Crown of Thorns", 1, "crown_of_thorns")
        p.equip(crown)
        p.traits.append(Trait("Trait", strength_bonus=0))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 1 + 1  # with crown
        p.unequip(crown)
        assert p.total_strength == 5  # no crown, no trait str bonus

    def test_combat_strength_includes_crown_hook(self):
        p = _player(base_strength=5)
        self._equip_crown(p)
        p.traits.append(Trait("T1", strength_bonus=0))
        p.traits.append(Trait("T2", strength_bonus=0))
        fx.refresh_tokens(p)
        # combat_strength should match total_strength (no consumables, not night)
        assert p.combat_strength() == p.total_strength


# ---------------------------------------------------------------------------
# Helmet slot mechanics
# ---------------------------------------------------------------------------

class TestHelmetSlotMechanics:

    def test_equip_fills_slot(self):
        p = _player()
        helm = _helm("Iron Helm", 2)
        assert p.equip(helm) is True
        assert helm in p.helmets

    def test_default_one_helmet_slot(self):
        p = _player()
        assert p.helmet_slots == 1

    def test_second_helmet_rejected_by_default(self):
        p = _player()
        p.equip(_helm("Helm A", 1))
        helm_b = _helm("Helm B", 2)
        assert p.equip(helm_b) is False
        assert helm_b not in p.helmets

    def test_extra_slot_via_trait(self):
        p = _player()
        p.traits.append(Trait("Crown Bearer", helmet_slot_bonus=1))
        assert p.helmet_slots == 2
        assert p.equip(_helm("Helm A", 1)) is True
        assert p.equip(_helm("Helm B", 2)) is True

    def test_unequip_removes_from_helmets(self):
        p = _player()
        helm = _helm("Squire's Helm", 4)
        p.equip(helm)
        assert helm in p.helmets
        p.unequip(helm)
        assert helm not in p.helmets

    def test_unequip_returns_false_if_not_equipped(self):
        p = _player()
        helm = _helm("Squire's Helm", 4)
        assert p.unequip(helm) is False

    def test_can_equip_returns_false_when_full(self):
        p = _player()
        p.equip(_helm("Helmet", 1))
        assert p.can_equip(_helm("Helmet2", 1)) is False

    def test_can_equip_returns_true_when_empty(self):
        p = _player()
        assert p.can_equip(_helm("Helmet", 1)) is True


# ---------------------------------------------------------------------------
# Pack system (helmets)
# ---------------------------------------------------------------------------

class TestHelmetPackSystem:

    def test_add_helmet_to_pack(self):
        p = _player()
        helm = _helm("Football Helmet", 5)
        assert p.add_to_pack(helm) is True
        assert helm in p.pack

    def test_helm_in_pack_not_counted_as_equipped(self):
        p = _player()
        helm = _helm("Football Helmet", 5)
        p.pack.append(helm)
        # Pack item not equipped — has_equipped_item should return False
        assert p.has_equipped_item("") is False
        assert helm not in p.helmets

    def test_pack_does_not_grant_strength(self):
        p = _player(base_strength=5)
        helm = _helm("Dragon Helm", 4)
        p.pack.append(helm)
        assert p.total_strength == 5  # pack items don't count


# ---------------------------------------------------------------------------
# Strength contributions
# ---------------------------------------------------------------------------

class TestHelmetStrength:

    def test_helmet_bonus_counted_in_total_strength(self):
        p = _player(base_strength=3)
        p.equip(_helm("Knight's Helm", 7))
        assert p.total_strength == 3 + 7

    def test_multiple_helmets_stack_when_slots_available(self):
        p = _player(base_strength=3)
        p.traits.append(Trait("Crown Bearer", helmet_slot_bonus=1))
        p.equip(_helm("Helm A", 2))
        p.equip(_helm("Helm B", 3))
        assert p.total_strength == 3 + 2 + 3

    def test_zero_strength_helmet_has_no_effect(self):
        p = _player(base_strength=5)
        p.equip(_helm("Dud Helm", 0))
        assert p.total_strength == 5

    def test_helmet_strength_in_combat_strength(self):
        p = _player(base_strength=4)
        p.equip(_helm("Swiss Guard Helmet", 5))
        assert p.combat_strength() == 9


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestHeadArmourIntegration:

    def test_game_turn_with_helmet_equipped(self):
        """Smoke test: full game turn completes without error when wearing a helmet."""
        g = Game(seed=11)
        p = g.player
        p.equip(_helm("Football Helmet", 5))
        p.movement_hand = [2]
        result = g.play_turn(card_index=0)
        assert result.moved_to >= result.moved_from

    def test_crown_of_thorns_during_combat(self):
        """Crown of Thorns trait bonus applies during a player-vs-monster strength check."""
        p = _player(base_strength=1)
        crown = _helm("Crown of Thorns", 1, "crown_of_thorns")
        p.equip(crown)
        p.traits.append(Trait("T", strength_bonus=0))
        p.traits.append(Trait("T2", strength_bonus=0))
        fx.refresh_tokens(p)
        # 1 (base) + 1 (crown base) + 2 (hook: 2 traits) = 4
        assert p.combat_strength() == 4

    def test_helmet_items_in_content_pools_are_all_helmets(self):
        """Spot-check: named helmets from the pool are flagged with HELMET slot."""
        for pool in (C.ITEM_POOL_L1, C.ITEM_POOL_L2, C.ITEM_POOL_L3):
            for item in pool:
                if item.name in {"Knight's Helm", "Iron Helm", "Dragon Helm",
                                 "Titan Helm", "Crown of Thorns", "Face Mask",
                                 "Football Helmet", "War Helm"}:
                    assert item.slot == EquipSlot.HELMET, (
                        f"{item.name} should be HELMET slot, got {item.slot}"
                    )

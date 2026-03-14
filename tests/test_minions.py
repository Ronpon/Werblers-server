"""Tests for the minion system.

Covers:
- Minion dataclass fields
- player.minions (no slot limit)
- Minion strength contribution to total_strength and combat_strength
- Skeletal Minion: buffs each other minion by +1 Str
- On-gain trait effects: grown_up, misunderstood, alpha, new_lord, overlord
- On-gain curse effect: together_forever (Lonely Teddy -2)
- Multiple Skeletal Minions
- Negative-bonus minion (Lonely Teddy)
"""

import pytest

from werblers_engine.types import Curse, EquipSlot, Item, Minion, Trait
from werblers_engine.player import Player
from werblers_engine import effects as fx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player(**kwargs) -> Player:
    return Player(**kwargs)


def _minion(name: str, bonus: int, effect_id: str = "") -> Minion:
    return Minion(name, strength_bonus=bonus, effect_id=effect_id)


def _log() -> list[str]:
    return []


# ---------------------------------------------------------------------------
# Minion dataclass
# ---------------------------------------------------------------------------

class TestMinionDataclass:

    def test_defaults(self):
        m = Minion("Test Minion")
        assert m.name == "Test Minion"
        assert m.strength_bonus == 0
        assert m.effect_id == ""

    def test_custom_values(self):
        m = Minion("Swamp Friend", strength_bonus=6, effect_id="skeletal_minion")
        assert m.strength_bonus == 6
        assert m.effect_id == "skeletal_minion"


# ---------------------------------------------------------------------------
# player.minions — no slot limit
# ---------------------------------------------------------------------------

class TestPlayerMinionsField:

    def test_minions_empty_by_default(self):
        p = _player()
        assert p.minions == []

    def test_can_add_any_number_of_minions(self):
        p = _player()
        for i in range(10):
            p.minions.append(_minion(f"Minion{i}", 1))
        assert len(p.minions) == 10

    def test_minions_independent_of_equip_slots(self):
        """Adding minions does not consume helmet/chest/legs/weapon slots."""
        p = _player()
        for i in range(5):
            p.minions.append(_minion(f"M{i}", 2))
        assert p.helmet_slots == 1
        assert p.chest_slots == 1
        assert p.legs_slots == 1
        assert p.weapon_hands == 2


# ---------------------------------------------------------------------------
# total_minion_strength
# ---------------------------------------------------------------------------

class TestTotalMinionStrength:

    def test_no_minions_returns_zero(self):
        p = _player()
        assert fx.total_minion_strength(p) == 0

    def test_single_minion_counts(self):
        p = _player()
        p.minions.append(_minion("Ted Bearson", 3))
        assert fx.total_minion_strength(p) == 3

    def test_multiple_minions_stack(self):
        p = _player()
        p.minions.append(_minion("Swamp Friend", 6))
        p.minions.append(_minion("Pet Velociraptor", 8))
        assert fx.total_minion_strength(p) == 14

    def test_negative_minion_reduces_total(self):
        p = _player()
        p.minions.append(_minion("Pet Velociraptor", 8))
        p.minions.append(_minion("Lonely Teddy", -2))
        assert fx.total_minion_strength(p) == 6

    def test_minion_wrangler_buffs_one_other(self):
        """Minion Wrangler: 1 other minion → +2 extra."""
        p = _player()
        p.minions.append(_minion("Minion Wrangler", 3, "minion_wrangler"))
        p.minions.append(_minion("Ted Bearson", 3))
        # base: 3 + 3 = 6; wrangler buffs 1 other → +2 extra = 8
        assert fx.total_minion_strength(p) == 8

    def test_minion_wrangler_buffs_two_others(self):
        """Minion Wrangler: 2 other minions → +4 extra."""
        p = _player()
        p.minions.append(_minion("Minion Wrangler", 3, "minion_wrangler"))
        p.minions.append(_minion("Swamp Friend", 7))
        p.minions.append(_minion("Demon Spawn", 8))
        # base: 3 + 7 + 8 = 18; wrangler buffs 2 others → +4 extra = 22
        assert fx.total_minion_strength(p) == 22

    def test_minion_wrangler_alone_no_bonus(self):
        """Minion Wrangler alone has no other minions to buff."""
        p = _player()
        p.minions.append(_minion("Minion Wrangler", 3, "minion_wrangler"))
        assert fx.total_minion_strength(p) == 3

    def test_two_minion_wranglers_buff_others(self):
        """Two Minion Wranglers: each buffs the non-wrangler others,
        but they don't buff each other (wrangler_count * other_count * 2)."""
        p = _player()
        p.minions.append(_minion("Minion Wrangler", 3, "minion_wrangler"))
        p.minions.append(_minion("Minion Wrangler", 3, "minion_wrangler"))
        p.minions.append(_minion("Ted Bearson", 3))
        # base: 3+3+3 = 9; wrangler_count=2, other_count=1 → +2*1*2 = 13
        assert fx.total_minion_strength(p) == 13


# ---------------------------------------------------------------------------
# Minion strength in player.total_strength and combat_strength
# ---------------------------------------------------------------------------

class TestMinionStrengthIntegration:

    def test_minion_counts_in_total_strength(self):
        p = _player(base_strength=5)
        p.minions.append(_minion("Swamp Friend", 6))
        assert p.total_strength == 11

    def test_minion_counts_in_combat_strength(self):
        p = _player(base_strength=5)
        p.minions.append(_minion("Demon Spawn", 7))
        assert p.combat_strength() == 12

    def test_minion_and_item_stack(self):
        p = _player(base_strength=5)
        p.equip(Item("Sword", EquipSlot.WEAPON, strength_bonus=3))
        p.minions.append(_minion("Pet Velociraptor", 8))
        assert p.total_strength == 5 + 3 + 8

    def test_wrangler_bonus_in_total_strength(self):
        p = _player(base_strength=5)
        p.minions.append(_minion("Minion Wrangler", 3, "minion_wrangler"))
        p.minions.append(_minion("Ted Bearson", 3))
        # 5 (base) + 3 + 3 (minions) + 2 (wrangler buff) = 13
        assert p.total_strength == 13

    def test_lonely_teddy_reduces_total(self):
        p = _player(base_strength=10)
        p.minions.append(_minion("Lonely Teddy", -2))
        assert p.total_strength == 8


# ---------------------------------------------------------------------------
# On-gain trait effects
# ---------------------------------------------------------------------------

class TestTraitOnGainMinions:

    def _gain_trait(self, p: Player, effect_id: str, name: str = "T") -> list[str]:
        log = _log()
        trait = Trait(name, effect_id=effect_id)
        fx.on_trait_gained(p, trait, log)
        return log

    def test_grown_up_grants_ted_bearson(self):
        p = _player()
        log = self._gain_trait(p, "grown_up", "I'm a Grown-up Now!")
        assert len(p.minions) == 1
        assert p.minions[0].name == "Ted Bearson"
        assert p.minions[0].strength_bonus == 3
        assert any("Ted Bearson" in line for line in log)

    def test_misunderstood_grants_swamp_friend(self):
        p = _player()
        log = self._gain_trait(p, "misunderstood", "Misunderstood")
        assert len(p.minions) == 1
        assert p.minions[0].name == "Swamp Friend"
        assert p.minions[0].strength_bonus == 7

    def test_alpha_grants_pet_velociraptor(self):
        p = _player()
        log = self._gain_trait(p, "alpha", "Alpha")
        assert len(p.minions) == 1
        assert p.minions[0].name == "Pet Velociraptor"
        assert p.minions[0].strength_bonus == 5

    def test_new_lord_grants_demon_spawn(self):
        p = _player()
        log = self._gain_trait(p, "new_lord", "New Lord")
        assert len(p.minions) == 1
        assert p.minions[0].name == "Demon Spawn"
        assert p.minions[0].strength_bonus == 6

    def test_overlord_grants_minion_wrangler(self):
        p = _player()
        log = self._gain_trait(p, "overlord", "Overlord")
        assert len(p.minions) == 1
        m = p.minions[0]
        assert m.name == "Minion Wrangler"
        assert m.strength_bonus == 3
        assert m.effect_id == "minion_wrangler"

    def test_gaining_multiple_minion_traits_stacks(self):
        """Multiple minion-granting traits can stack (unlimited slots)."""
        p = _player()
        self._gain_trait(p, "grown_up")
        self._gain_trait(p, "alpha")
        self._gain_trait(p, "new_lord")
        assert len(p.minions) == 3

    def test_overlord_wrangler_buffs_existing_minions(self):
        """Overlord + another minion: wrangler buffs the other."""
        p = _player(base_strength=1)
        self._gain_trait(p, "grown_up")    # +3 Ted Bearson
        self._gain_trait(p, "overlord")    # +3 Minion Wrangler
        # minion total: 3 + 3 + 2 (wrangler buffs Ted) = 8
        assert fx.total_minion_strength(p) == 8
        assert p.total_strength == 1 + 8


# ---------------------------------------------------------------------------
# On-gain curse effects
# ---------------------------------------------------------------------------

class TestCurseOnGainMinions:

    def _gain_curse(self, p: Player, effect_id: str, name: str = "C") -> list[str]:
        log = _log()
        curse = Curse(name, effect_id=effect_id)
        fx.on_curse_gained(p, curse, log)
        return log

    def test_together_forever_grants_lonely_teddy_minion(self):
        p = _player()
        log = self._gain_curse(p, "together_forever", "Together Forever!")
        assert len(p.minions) == 1
        m = p.minions[0]
        assert m.name == "Lonely Teddy"
        assert m.strength_bonus == -2
        assert any("Lonely Teddy" in line for line in log)

    def test_lonely_teddy_reduces_minion_strength(self):
        """Lonely Teddy as minion contributes -2 to minion strength total."""
        p = _player(base_strength=10)
        self._gain_curse(p, "together_forever")
        assert fx.total_minion_strength(p) == -2

    def test_lonely_teddy_minion_with_other_minions(self):
        """Lonely Teddy as minion applies -2 alongside other minion bonuses."""
        p = _player(base_strength=5)
        self._gain_curse(p, "together_forever")   # Lonely Teddy minion (-2)
        p.minions.append(_minion("Ted Bearson", 3))
        assert fx.total_minion_strength(p) == 1  # -2 + 3 = 1

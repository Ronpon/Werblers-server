"""Tests for the monster-specific trait/curse effect system.

Covers:
- Monster → trait/curse factory functions
- Conditional strength bonuses (traits and curses)
- Movement card modifications
- On-gain one-time effects (equipment destruction, move-back, item grants)
- Hand size cap from curses
- Integration with encounter flow
"""

import pytest

from werblers_engine.types import (
    CombatResult,
    Curse,
    EquipSlot,
    Item,
    Monster,
    Trait,
)
from werblers_engine.player import Player
from werblers_engine import content as C
from werblers_engine import effects as fx


# ===================================================================
# Helpers
# ===================================================================

def _make_player(**kwargs) -> Player:
    """Shortcut to create a Player with optional overrides."""
    return Player(**kwargs)


def _equip(player: Player, name: str, slot: EquipSlot, bonus: int = 1) -> Item:
    item = Item(name, slot, strength_bonus=bonus)
    player.equip(item)
    return item


# ===================================================================
# Monster → Trait / Curse factory
# ===================================================================

class TestMonsterTraitCurseFactory:
    """trait_for_monster() / curse_for_monster() produce correct objects."""

    def test_trait_for_known_monster(self):
        m = Monster("Attack Turtle", strength=2, level=1, trait_name="Hard Shell")
        t = C.trait_for_monster(m)
        assert t is not None
        assert t.name == "Hard Shell"
        assert t.strength_bonus == 2
        assert t.source_monster == "Attack Turtle"

    def test_curse_for_known_monster(self):
        m = Monster("Big Rat", strength=3, level=1, curse_name="Bit o' the Plague")
        c = C.curse_for_monster(m)
        assert c is not None
        assert c.name == "Bit o' the Plague"
        assert c.strength_bonus == -2
        assert c.source_monster == "Big Rat"

    def test_trait_for_monster_with_effect_id(self):
        m = Monster("Nose Goblin", strength=1, level=1, trait_name="Calloused")
        t = C.trait_for_monster(m)
        assert t.effect_id == "calloused"

    def test_curse_for_monster_with_effect_id(self):
        m = Monster("Rusty Golem", strength=6, level=1, curse_name="The Rust is Spreading!")
        c = C.curse_for_monster(m)
        assert c.effect_id == "rust_spreading"

    def test_no_trait_for_monster_without_trait_name(self):
        m = Monster("Placeholder Rat", strength=2, level=1)
        assert C.trait_for_monster(m) is None

    def test_no_curse_for_monster_without_curse_name(self):
        m = Monster("Placeholder Rat", strength=2, level=1)
        assert C.curse_for_monster(m) is None

    def test_all_30_monsters_have_entries(self):
        """Every monster in ALL_MONSTERS maps to a trait and curse."""
        for m in C.ALL_MONSTERS:
            t = C.trait_for_monster(m)
            c = C.curse_for_monster(m)
            assert t is not None, f"{m.name} has no trait"
            assert c is not None, f"{m.name} has no curse"
            assert t.source_monster == m.name
            assert c.source_monster == m.name


# ===================================================================
# Trait — Conditional strength bonuses
# ===================================================================

class TestTraitStrengthEffects:

    def test_calloused_no_helmet(self):
        """Calloused: +3 Str when wearing no helmet."""
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Calloused", effect_id="calloused"))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 3

    def test_calloused_with_helmet(self):
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Calloused", effect_id="calloused"))
        _equip(p, "Iron Helm", EquipSlot.HELMET, bonus=2)
        assert p.total_strength == 5 + 2  # no calloused bonus, just helm

    def test_bde_no_legs(self):
        """BDE: +5 Str when wearing no leg armour."""
        p = _make_player(base_strength=5)
        p.traits.append(Trait("BDE", effect_id="bde"))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 5

    def test_bde_with_legs(self):
        """BDE: no bonus when wearing leg armour."""
        p = _make_player(base_strength=5)
        p.traits.append(Trait("BDE", effect_id="bde"))
        _equip(p, "Greaves", EquipSlot.LEGS, bonus=2)
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 2  # no BDE bonus, just greaves

    def test_tough_skin_empty_pack(self):
        """Tough Skin: +0 Str when pack is empty."""
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Tough Skin", effect_id="tough_skin"))
        fx.refresh_tokens(p)
        assert p.total_strength == 5

    def test_tough_skin_counts_pack_items(self):
        """Tough Skin: +1 Str per item in pack (equip, consumable, captured monster)."""
        from werblers_engine.types import Consumable
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Tough Skin", effect_id="tough_skin"))
        p.pack.append(Item("Helmet", EquipSlot.HELMET, strength_bonus=0))
        p.consumables.append(Consumable("Potion", effect_id="potion"))
        p.captured_monsters.append(Monster("Goblin", strength=1, effect_id="goblin"))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + 3  # 1 pack + 1 consumable + 1 captured

    def test_bark_worse_than_bite_empty_slots(self):
        """Bark Worse Than its Bite: +3 per empty equip slot."""
        p = _make_player(base_strength=1)
        p.traits.append(Trait("Bark", effect_id="bark_worse_than_bite"))
        fx.refresh_tokens(p)
        # Default: 1 helm + 1 chest + 1 legs + 2 weapons = 5 slots, all empty
        assert p.total_strength == 1 + (3 * 5)

    def test_bark_worse_than_bite_some_equipped(self):
        p = _make_player(base_strength=1)
        p.traits.append(Trait("Bark", effect_id="bark_worse_than_bite"))
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=2)
        _equip(p, "Helm", EquipSlot.HELMET, bonus=1)
        # 3 empty slots: chest(1), legs(1), weapon(1)
        assert p.total_strength == 1 + 2 + 1 + (3 * 3)

    def test_strengthened_by_taint(self):
        """Strengthened by Taint: +2 per curse."""
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Taint", effect_id="strengthened_by_taint"))
        p.curses.append(Curse("C1"))
        p.curses.append(Curse("C2"))
        p.curses.append(Curse("C3"))
        fx.refresh_tokens(p)
        assert p.total_strength == 5 + (2 * 3)

    def test_flat_strength_trait(self):
        """Hard Shell / Stomach of Steel: plain +N Str."""
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Hard Shell", strength_bonus=2))
        assert p.total_strength == 7

    def test_hand_size_bonus_trait(self):
        """My Hands are Awesome: hand size +1 (base 4 + 1 = 5)."""
        p = _make_player()
        p.traits.append(Trait("My Hands", hand_size_bonus=1))
        assert p.effective_max_hand_size == 5

    def test_chest_slot_bonus_trait(self):
        """Big Boned: +1 chest slot."""
        p = _make_player()
        p.traits.append(Trait("Big Boned", chest_slot_bonus=1))
        assert p.chest_slots == 2


# ===================================================================
# Curse — Conditional strength bonuses
# ===================================================================

class TestCurseStrengthEffects:

    def test_nevernude_all_slots_empty(self):
        """Nevernude: -5 Str per empty equip slot."""
        p = _make_player(base_strength=30)
        p.curses.append(Curse("Nevernude", effect_id="nevernude"))
        fx.refresh_tokens(p)
        # 5 empty slots → -25
        assert p.total_strength == 30 - 25

    def test_nevernude_some_equipped(self):
        p = _make_player(base_strength=30)
        p.curses.append(Curse("Nevernude", effect_id="nevernude"))
        _equip(p, "Helm", EquipSlot.HELMET, bonus=2)
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=3)
        # 3 empty (chest, legs, 1 weapon) → -15
        assert p.total_strength == 30 + 2 + 3 - 15

    def test_facial_coverings_no_helmet(self):
        """Facial Coverings Required: -10 Str with no helmet."""
        p = _make_player(base_strength=15)
        p.curses.append(Curse("Facial Cov.", effect_id="facial_coverings"))
        fx.refresh_tokens(p)
        assert p.total_strength == 5

    def test_facial_coverings_with_helmet(self):
        p = _make_player(base_strength=15)
        p.curses.append(Curse("Facial Cov.", effect_id="facial_coverings"))
        _equip(p, "Helm", EquipSlot.HELMET, bonus=2)
        assert p.total_strength == 17  # no penalty

    def test_stabbed_scales_with_curses(self):
        """Stabbed: -1 Str per curse (including itself)."""
        p = _make_player(base_strength=10)
        p.curses.append(Curse("Other Curse"))
        stabbed = Curse("Stabbed", effect_id="stabbed")
        p.curses.append(stabbed)
        fx.refresh_tokens(p)
        # 2 curses → -2
        assert p.total_strength == 8

    def test_flat_strength_curse(self):
        p = _make_player(base_strength=10)
        p.curses.append(Curse("Bit More Plague", strength_bonus=-3))
        assert p.total_strength == 7

    def test_strength_cannot_go_negative(self):
        p = _make_player(base_strength=1)
        p.curses.append(Curse("Termites", strength_bonus=-5))
        assert p.total_strength == 0  # clamped to 0


# ===================================================================
# Movement card modification
# ===================================================================

class TestMovementModification:

    def test_yer_a_hare_6_becomes_1(self):
        """Yer a Hare, Wizard: 6 → 1."""
        p = _make_player()
        p.curses.append(Curse("Hare", effect_id="yer_a_hare"))
        assert fx.modify_movement_value(p, 6) == 1

    def test_yer_a_hare_other_values_unaffected(self):
        p = _make_player()
        p.curses.append(Curse("Hare", effect_id="yer_a_hare"))
        for v in [1, 2, 3, 4, 5]:
            assert fx.modify_movement_value(p, v) == v

    def test_botched_circumcision_minus_1(self):
        """Botched Circumcision: all cards -1, min 1."""
        p = _make_player()
        p.curses.append(Curse("Botched", effect_id="botched_circumcision"))
        assert fx.modify_movement_value(p, 5) == 4
        assert fx.modify_movement_value(p, 3) == 2
        assert fx.modify_movement_value(p, 1) == 1  # min 1

    def test_eughghghghgh_1_becomes_0(self):
        """Eughghghghgh: 1 → 0 when more curses than traits."""
        p = _make_player()
        p.curses.append(Curse("Eugh", effect_id="eughghghghgh"))
        # 1 curse, 0 traits → condition met
        assert fx.modify_movement_value(p, 1) == 0

    def test_eughghghghgh_not_active_when_balanced(self):
        """Eughghghghgh: no effect when curses ≤ traits."""
        p = _make_player()
        p.curses.append(Curse("Eugh", effect_id="eughghghghgh"))
        p.traits.append(Trait("Some Trait"))
        # 1 curse, 1 trait → condition NOT met
        assert fx.modify_movement_value(p, 1) == 1

    def test_eughghghghgh_only_affects_1s(self):
        p = _make_player()
        p.curses.append(Curse("Eugh", effect_id="eughghghghgh"))
        assert fx.modify_movement_value(p, 3) == 3

    def test_scared_of_dark_at_night(self):
        """Scared of the Dark: at night, -1 movement."""
        p = _make_player()
        p.curses.append(Curse("Scared", effect_id="scared_of_dark"))
        assert fx.modify_movement_value(p, 4, is_night=True) == 3
        assert fx.modify_movement_value(p, 1, is_night=True) == 0

    def test_scared_of_dark_during_day(self):
        p = _make_player()
        p.curses.append(Curse("Scared", effect_id="scared_of_dark"))
        assert fx.modify_movement_value(p, 4, is_night=False) == 4

    def test_no_curses_no_modification(self):
        p = _make_player()
        assert fx.modify_movement_value(p, 5) == 5

    def test_stacked_adjustments(self):
        """Multiple movement curses stack."""
        p = _make_player()
        p.curses.append(Curse("Botched", effect_id="botched_circumcision"))
        p.curses.append(Curse("Scared", effect_id="scared_of_dark"))
        # At night: -1 (botched) + -1 (scared) = -2, but botched min 1
        assert fx.modify_movement_value(p, 3, is_night=True) == 1
        # During day: only botched applies
        assert fx.modify_movement_value(p, 3, is_night=False) == 2


# ===================================================================
# Hand size cap
# ===================================================================

class TestHandSizeCap:

    def test_dude_wheres_my_card_caps_at_3(self):
        p = _make_player()
        p.curses.append(Curse("Dude", effect_id="dude_wheres_my_card"))
        assert p.effective_max_hand_size == 3  # base is 4, but capped at 3

    def test_dude_wheres_my_card_overrides_trait_bonus(self):
        p = _make_player()
        p.traits.append(Trait("My Hands", hand_size_bonus=1))  # would be 5 without curse
        p.curses.append(Curse("Dude", effect_id="dude_wheres_my_card"))
        assert p.effective_max_hand_size == 3  # capped

    def test_no_cap_without_curse(self):
        p = _make_player()
        p.traits.append(Trait("My Hands", hand_size_bonus=1))
        assert p.effective_max_hand_size == 5


# ===================================================================
# On-gain: Trait effects
# ===================================================================

class TestOnTraitGained:

    def test_ball_and_chain_equips_weapon(self):
        p = _make_player()
        trait = Trait("Ball and Chain", effect_id="ball_and_chain")
        log: list[str] = []
        fx.on_trait_gained(p, trait, log)
        assert len(p.weapons) == 1
        assert p.weapons[0].name == "Ball and Chain"
        assert p.weapons[0].strength_bonus == 7

    def test_ball_and_chain_no_slot(self):
        p = _make_player()
        _equip(p, "Sword1", EquipSlot.WEAPON, bonus=1)
        _equip(p, "Sword2", EquipSlot.WEAPON, bonus=1)
        trait = Trait("Ball and Chain", effect_id="ball_and_chain")
        log: list[str] = []
        fx.on_trait_gained(p, trait, log)
        assert len(p.weapons) == 2  # no room
        assert "no slot" in log[0]

    def test_birdie_equips_weapon(self):
        p = _make_player()
        trait = Trait("You Got a Birdie!", effect_id="birdie")
        log: list[str] = []
        fx.on_trait_gained(p, trait, log)
        assert len(p.weapons) == 1
        assert p.weapons[0].name == "Power Driver"
        assert p.weapons[0].strength_bonus == 10

    def test_kapwing_equips_chest(self):
        p = _make_player()
        trait = Trait("Kapwing!", effect_id="kapwing")
        log: list[str] = []
        fx.on_trait_gained(p, trait, log)
        assert len(p.chest_armor) == 1
        assert p.chest_armor[0].name == "Bulletproof Vest"
        assert p.chest_armor[0].strength_bonus == 8

    def test_deferred_trait_logs_message(self):
        p = _make_player()
        trait = Trait("I'm a Grown-up Now!", effect_id="grown_up")
        log: list[str] = []
        fx.on_trait_gained(p, trait, log)
        # grown_up now grants Ted Bearson minion — check minion was added
        assert len(p.minions) == 1
        assert p.minions[0].name == "Ted Bearson"


# ===================================================================
# On-gain: Curse effects — equipment destruction
# ===================================================================

class TestOnCurseEquipDestruction:

    def test_it_got_in_discards_legs(self):
        p = _make_player()
        _equip(p, "Greaves", EquipSlot.LEGS, bonus=2)
        curse = Curse("It Got In!", effect_id="it_got_in")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.leg_armor) == 0

    def test_rust_spreading_discards_weapons(self):
        p = _make_player()
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=3)
        _equip(p, "Shield", EquipSlot.WEAPON, bonus=2)
        curse = Curse("Rust!", effect_id="rust_spreading")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.weapons) == 0

    def test_dont_look_up_discards_helmet(self):
        p = _make_player()
        _equip(p, "Iron Helm", EquipSlot.HELMET, bonus=2)
        curse = Curse("Don't look up!", effect_id="dont_look_up")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.helmets) == 0

    def test_need_a_place_discards_boots(self):
        p = _make_player()
        _equip(p, "Boots", EquipSlot.LEGS, bonus=1)
        curse = Curse("I Need a Place to Go!", effect_id="need_a_place")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.leg_armor) == 0

    def test_laundry_day_discards_all_armor(self):
        p = _make_player()
        _equip(p, "Helm", EquipSlot.HELMET, bonus=1)
        _equip(p, "Mail", EquipSlot.CHEST, bonus=3)
        _equip(p, "Greaves", EquipSlot.LEGS, bonus=2)
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=4)  # not armor
        curse = Curse("Laundry Day!", effect_id="laundry_day")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.helmets) == 0
        assert len(p.chest_armor) == 0
        assert len(p.leg_armor) == 0
        assert len(p.weapons) == 1  # weapons NOT affected

    def test_smell_wont_come_out_discards_2(self):
        p = _make_player()
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=2)
        _equip(p, "Shield", EquipSlot.WEAPON, bonus=1)
        _equip(p, "Helm", EquipSlot.HELMET, bonus=1)
        curse = Curse("Smell!", effect_id="smell_wont_come_out")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        # Should discard 2, preferring weapons first
        total_remaining = len(p.weapons) + len(p.helmets)
        assert total_remaining == 1

    def test_drink_tastes_funny_discards_2(self):
        p = _make_player()
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=3)
        _equip(p, "Helm", EquipSlot.HELMET, bonus=2)
        _equip(p, "Greaves", EquipSlot.LEGS, bonus=1)
        curse = Curse("Drink!", effect_id="drink_tastes_funny")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        total = len(p.weapons) + len(p.helmets) + len(p.leg_armor)
        assert total == 1  # 3 items - 2 discarded = 1

    def test_shot_through_heart_with_chest(self):
        """With chest: discard it, place Gunshot Wound item."""
        p = _make_player(base_strength=10)
        _equip(p, "Mail", EquipSlot.CHEST, bonus=3)
        curse = Curse("Shot!", effect_id="shot_through_heart", strength_bonus=-5)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.chest_armor) == 1
        assert p.chest_armor[0].name == "Gunshot Wound"
        assert p.chest_armor[0].strength_bonus == -3
        assert curse.strength_bonus == 0  # mutated to 0; penalty from item

    def test_shot_through_heart_without_chest(self):
        """Without chest: places Gunshot Wound item in chest slot, no permanent -5."""
        p = _make_player(base_strength=10)
        curse = Curse("Shot!", effect_id="shot_through_heart", strength_bonus=-5)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.chest_armor) == 1
        assert p.chest_armor[0].name == "Gunshot Wound"
        assert p.chest_armor[0].strength_bonus == -3
        p.curses.append(curse)
        # base 10 + chest item -3 + curse 0 = 7
        assert p.total_strength == 7

    def test_the_rack_discards_per_curse(self):
        """The Rack: discard 1 trait/equip per curse."""
        p = _make_player()
        p.traits.append(Trait("T1"))
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=1)
        p.curses.append(Curse("Old Curse"))
        rack = Curse("Rack!", effect_id="the_rack")
        p.curses.append(rack)
        log: list[str] = []
        fx.on_curse_gained(p, rack, log)
        # 2 curses → discard 2 (trait first, then equip)
        assert len(p.traits) == 0
        assert len(p.weapons) == 0

    def test_no_equipment_no_error(self):
        """Destruction curses gracefully handle no equipment."""
        p = _make_player()
        curse = Curse("Rust!", effect_id="rust_spreading")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)  # should not raise


# ===================================================================
# On-gain: Curse effects — move backward
# ===================================================================

class TestOnCurseMoveBack:

    def test_roughing_kicker_back_15(self):
        p = _make_player()
        p.position = 70
        curse = Curse("Roughing!", effect_id="roughing_kicker")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.position == 55

    def test_roughing_kicker_clamped_at_1(self):
        p = _make_player()
        p.position = 10
        curse = Curse("Roughing!", effect_id="roughing_kicker")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.position == 1

    def test_blacklisted_back_to_start(self):
        p = _make_player()
        p.position = 80
        curse = Curse("Blacklisted!", effect_id="blacklisted")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.position == 1

    def test_quite_setback_back_10_and_discard(self):
        p = _make_player()
        p.position = 50
        p.movement_hand = [1, 3, 4, 2, 3]
        curse = Curse("Setback!", effect_id="quite_setback")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.position == 40
        assert 3 not in p.movement_hand
        assert 4 not in p.movement_hand
        assert p.movement_hand == [1, 2]


# ===================================================================
# On-gain: Hand size curse
# ===================================================================

class TestOnCurseHandSize:

    def test_dude_wheres_my_card_discards_excess(self):
        p = _make_player()
        p.movement_hand = [1, 2, 3, 4, 5]
        curse = Curse("Dude", effect_id="dude_wheres_my_card")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.movement_hand) == 3

    def test_dude_wheres_my_card_no_excess(self):
        p = _make_player()
        p.movement_hand = [1, 2]
        curse = Curse("Dude", effect_id="dude_wheres_my_card")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.movement_hand) == 2  # no change


# ===================================================================
# Integration: encounter delivers monster-specific traits/curses
# ===================================================================

class TestEncounterIntegration:

    def test_monster_win_gives_specific_trait(self):
        """Winning against a named monster gives that monster's trait."""
        from werblers_engine.deck import Deck
        from werblers_engine import encounters as enc

        p = _make_player(base_strength=20)
        # Create a deck with Attack Turtle (Str 2, trait: Hard Shell +2)
        turtle = Monster(
            "Attack Turtle", strength=2, level=1,
            trait_name="Hard Shell", trait_text="You have +2 Str.",
        )
        monster_deck = Deck([turtle], seed=1)
        trait_deck = Deck([Trait("Generic")], seed=1)
        curse_deck = Deck([Curse("Generic")], seed=1)
        log: list[str] = []

        result = enc.encounter_monster(p, monster_deck, trait_deck, curse_deck, log)

        assert result == CombatResult.WIN
        assert len(p.traits) == 1
        assert p.traits[0].name == "Hard Shell"
        assert p.traits[0].strength_bonus == 2
        assert p.traits[0].source_monster == "Attack Turtle"

    def test_monster_loss_gives_specific_curse(self):
        """Losing to a named monster gives that monster's curse."""
        from werblers_engine.deck import Deck
        from werblers_engine import encounters as enc

        p = _make_player(base_strength=1)
        golem = Monster(
            "Rusty Golem", strength=6, level=1,
            curse_name="The Rust is Spreading!",
            curse_text="Discard all equipped Weapons.",
        )
        _equip(p, "Sword", EquipSlot.WEAPON, bonus=2)
        monster_deck = Deck([golem], seed=1)
        trait_deck = Deck([Trait("Generic")], seed=1)
        curse_deck = Deck([Curse("Generic")], seed=1)
        log: list[str] = []

        result = enc.encounter_monster(p, monster_deck, trait_deck, curse_deck, log)

        assert result == CombatResult.LOSE
        assert len(p.curses) == 1
        assert p.curses[0].name == "The Rust is Spreading!"
        assert p.curses[0].effect_id == "rust_spreading"
        assert len(p.weapons) == 0  # on-gain effect triggered

    def test_placeholder_monster_uses_random_pool(self):
        """Placeholder monsters (no trait_name) fall back to random pool."""
        from werblers_engine.deck import Deck
        from werblers_engine import encounters as enc

        p = _make_player(base_strength=20)
        placeholder = Monster("Placeholder Rat", strength=2, level=1)
        monster_deck = Deck([placeholder], seed=1)
        generic_trait = Trait("Strong Arm", strength_bonus=1)
        trait_deck = Deck([generic_trait], seed=1)
        curse_deck = Deck([Curse("Generic")], seed=1)
        log: list[str] = []

        result = enc.encounter_monster(p, monster_deck, trait_deck, curse_deck, log)

        assert result == CombatResult.WIN
        assert len(p.traits) == 1
        assert p.traits[0].name == "Strong Arm"  # from random pool

    def test_on_gain_item_via_encounter(self):
        """Winning yields trait + on-gain item (e.g. Ball and Chain)."""
        from werblers_engine.deck import Deck
        from werblers_engine import encounters as enc

        p = _make_player(base_strength=20)
        wrecking_ball = Monster(
            "Wrecking Ball", strength=8, level=1,
            trait_name="Ball and Chain",
            trait_text='Take the "Ball and Chain" Item card (+7 Str. 1 handed).',
        )
        monster_deck = Deck([wrecking_ball], seed=1)
        trait_deck = Deck([Trait("Generic")], seed=1)
        curse_deck = Deck([Curse("Generic")], seed=1)
        log: list[str] = []

        enc.encounter_monster(p, monster_deck, trait_deck, curse_deck, log)

        assert len(p.traits) == 1
        assert p.traits[0].name == "Ball and Chain"
        assert len(p.weapons) == 1
        assert p.weapons[0].name == "Ball and Chain"
        assert p.weapons[0].strength_bonus == 7

    def test_move_back_curse_via_encounter(self):
        """Losing triggers on-gain move-back (e.g. Roughing the Kicker)."""
        from werblers_engine.deck import Deck
        from werblers_engine import encounters as enc

        p = _make_player(base_strength=1)
        p.position = 70
        linebacker = Monster(
            "Zombie Linebacker", strength=22, level=3,
            curse_name="Roughing the Kicker!",
            curse_text="Move back 15 spaces.",
        )
        monster_deck = Deck([linebacker], seed=1)
        trait_deck = Deck([Trait("Generic")], seed=1)
        curse_deck = Deck([Curse("Generic")], seed=1)
        log: list[str] = []

        enc.encounter_monster(p, monster_deck, trait_deck, curse_deck, log)

        assert p.position == 55  # 70 - 15


# ===================================================================
# Integration: combat_strength includes effect bonuses
# ===================================================================

class TestCombatStrengthWithEffects:

    def test_combat_strength_includes_trait_effects(self):
        p = _make_player(base_strength=5)
        p.traits.append(Trait("Calloused", effect_id="calloused"))
        fx.refresh_tokens(p)
        assert p.combat_strength() == 8  # 5 + 3 (no helmet)

    def test_combat_strength_includes_curse_effects(self):
        p = _make_player(base_strength=20)
        p.curses.append(Curse("Facial Cov.", effect_id="facial_coverings"))
        fx.refresh_tokens(p)
        assert p.combat_strength() == 10  # 20 - 10 (no helmet)

    def test_combat_strength_night_aware(self):
        """Scared of the Dark is movement-only, not strength."""
        p = _make_player(base_strength=10)
        p.curses.append(Curse("Scared", effect_id="scared_of_dark"))
        # scared_of_dark only affects movement, not strength
        assert p.combat_strength(is_night=True) == 10


# ===================================================================
# Pack effects
# ===================================================================

class TestPackEffects:

    def test_flooded_base_clears_pack(self):
        p = _make_player()
        p.pack.append(Item("Sword", EquipSlot.WEAPON, strength_bonus=3))
        p.pack.append(Item("Helm", EquipSlot.HELMET, strength_bonus=2))
        curse = Curse("They Flooded Your Base!", effect_id="flooded_base")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.pack == []
        assert any("discarded" in msg for msg in log)

    def test_flooded_base_empty_pack_no_error(self):
        p = _make_player()
        curse = Curse("They Flooded Your Base!", effect_id="flooded_base")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.pack == []
        assert any("already empty" in msg for msg in log)

    def test_clever_girl_clears_pack(self):
        p = _make_player()
        p.pack.append(Item("Boots", EquipSlot.LEGS, strength_bonus=1))
        curse = Curse("Clever Girl\u2026", effect_id="clever_girl")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.pack == []

    def test_out_of_phase_trims_pack_to_1(self):
        p = _make_player()
        p.pack.append(Item("A", EquipSlot.WEAPON, strength_bonus=1))
        p.pack.append(Item("B", EquipSlot.HELMET, strength_bonus=1))
        p.pack.append(Item("C", EquipSlot.LEGS, strength_bonus=1))
        curse = Curse("Out of Phase", effect_id="out_of_phase")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.pack) == 1

    def test_out_of_phase_pack_size_is_1(self):
        p = _make_player()
        p.curses.append(Curse("Out of Phase", effect_id="out_of_phase"))
        assert p.pack_size == 1

    def test_out_of_phase_blocks_add_to_pack(self):
        p = _make_player()
        p.curses.append(Curse("Out of Phase", effect_id="out_of_phase"))
        result1 = p.add_to_pack(Item("A", EquipSlot.WEAPON))
        assert result1 is True
        result2 = p.add_to_pack(Item("B", EquipSlot.WEAPON))
        assert result2 is False
        assert len(p.pack) == 1

    def test_normal_pack_size_without_curse(self):
        p = _make_player()
        assert p.pack_size == 3


# ===================================================================
# Cursed! — auto-lose next battle
# ===================================================================

class TestCursedAutoLose:

    def test_flag_set_on_curse_gain(self):
        from werblers_engine import effects as fx
        p = _make_player()
        curse = Curse("Cursed!", effect_id="cursed_auto_lose")
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.auto_loses_next_battle is True

    def test_auto_lose_overrides_strong_player(self):
        from werblers_engine.combat import resolve_combat
        from werblers_engine.types import CombatResult
        p = _make_player(base_strength=100)
        p.auto_loses_next_battle = True
        monster = Monster("Weak Rat", strength=1, level=1)
        result = resolve_combat(p, monster)
        assert result == CombatResult.LOSE

    def test_flag_consumed_after_one_battle(self):
        from werblers_engine.combat import resolve_combat
        p = _make_player(base_strength=100)
        p.auto_loses_next_battle = True
        monster = Monster("Weak Rat", strength=1, level=1)
        resolve_combat(p, monster)  # first fight: auto-lose
        assert p.auto_loses_next_battle is False

    def test_second_battle_uses_normal_strength(self):
        from werblers_engine.combat import resolve_combat
        from werblers_engine.types import CombatResult
        p = _make_player(base_strength=100)
        p.auto_loses_next_battle = True
        monster = Monster("Weak Rat", strength=1, level=1)
        resolve_combat(p, monster)  # first: auto-lose
        result2 = resolve_combat(p, monster)  # second: normal
        assert result2 == CombatResult.WIN


# ===================================================================
# It's Wriggling! — discard a trait on curse gain
# ===================================================================

class TestItsWriggling:
    """It's Wriggling! is a persistent trigger: whenever a NEW curse arrives
    while the player already has It's Wriggling, a trait is discarded.
    The check now lives in encounters._apply_curse rather than
    effects.on_curse_gained.
    """

    def test_wriggling_removes_trait_on_next_curse(self):
        from werblers_engine import encounters as enc
        p = _make_player()
        p.traits.append(Trait("Strong Arm", strength_bonus=2))
        p.traits.append(Trait("Calloused", effect_id="calloused"))
        # Give the player It's Wriggling first
        wriggling = Curse("It's Wriggling!", effect_id="its_wriggling")
        p.curses.append(wriggling)
        # Now a NEW curse arrives — should trigger Wriggling
        new_curse = Curse("Some Curse")
        log: list[str] = []
        enc._apply_curse(p, new_curse, None, log)
        assert len(p.traits) == 1
        assert any("Wriggling" in msg for msg in log)

    def test_wriggling_no_traits_no_error(self):
        from werblers_engine import encounters as enc
        p = _make_player()
        wriggling = Curse("It's Wriggling!", effect_id="its_wriggling")
        p.curses.append(wriggling)
        new_curse = Curse("Some Curse")
        log: list[str] = []
        enc._apply_curse(p, new_curse, None, log)
        assert p.traits == []


# ===================================================================
# Monster pool — derived from ALL_MONSTERS
# ===================================================================

class TestMonsterPools:

    def test_l1_pool_contains_only_level_1(self):
        assert all(m.level == 1 for m in C.MONSTER_POOL_L1)

    def test_l2_pool_contains_only_level_2(self):
        assert all(m.level == 2 for m in C.MONSTER_POOL_L2)

    def test_l3_pool_contains_only_level_3(self):
        assert all(m.level == 3 for m in C.MONSTER_POOL_L3)

    def test_pools_non_empty(self):
        assert len(C.MONSTER_POOL_L1) > 0
        assert len(C.MONSTER_POOL_L2) > 0
        assert len(C.MONSTER_POOL_L3) > 0

    def test_all_pool_monsters_have_trait_and_curse_names(self):
        for pool in (C.MONSTER_POOL_L1, C.MONSTER_POOL_L2, C.MONSTER_POOL_L3):
            for m in pool:
                assert m.trait_name, f"{m.name} missing trait_name"
                assert m.curse_name, f"{m.name} missing curse_name"

    def test_pools_cover_all_real_monsters(self):
        total = len(C.MONSTER_POOL_L1) + len(C.MONSTER_POOL_L2) + len(C.MONSTER_POOL_L3)
        assert total == len(C.ALL_MONSTERS)


# ===================================================================
# Locked Item — unequip blocked while anchoring curse is active
# ===================================================================

class TestLockedItem:

    def test_locked_item_cannot_be_unequipped(self):
        p = _make_player()
        shoes = Item("Dancing Shoes", EquipSlot.LEGS, strength_bonus=1,
                     locked_by_curse_id="cant_stop_music")
        p.leg_armor.append(shoes)
        curse = Curse("Can't Stop the Music!", effect_id="cant_stop_music")
        p.curses.append(curse)
        assert p.unequip(shoes) is False
        assert shoes in p.leg_armor

    def test_locked_item_can_be_unequipped_after_curse_removed(self):
        p = _make_player()
        shoes = Item("Dancing Shoes", EquipSlot.LEGS, strength_bonus=1,
                     locked_by_curse_id="cant_stop_music")
        p.leg_armor.append(shoes)
        # No active curse — can unequip
        assert p.unequip(shoes) is True
        assert shoes not in p.leg_armor

    def test_unlocked_item_unequips_normally(self):
        p = _make_player()
        helmet = _equip(p, "Iron Helm", EquipSlot.HELMET)
        assert p.unequip(helmet) is True
        assert helmet not in p.helmets


# ===================================================================
# Its Taking Over — discard leg and chest armour on gain
# ===================================================================

class TestItsTakingOver:

    def test_discards_leg_and_chest_on_gain(self):
        p = _make_player()
        _equip(p, "Iron Greaves", EquipSlot.LEGS, bonus=3)
        _equip(p, "Leather Armour", EquipSlot.CHEST, bonus=2)
        curse = Curse("It's Taking Over!", effect_id="its_taking_over", strength_bonus=0)
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.leg_armor == []
        assert p.chest_armor == []
        assert any("discarded" in msg for msg in log)

    def test_no_armor_logs_nothing_discarded(self):
        p = _make_player()
        curse = Curse("It's Taking Over!", effect_id="its_taking_over", strength_bonus=0)
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.leg_armor == []
        assert p.chest_armor == []
        assert any("nothing discarded" in msg for msg in log)

    def test_only_legs_cleared_if_no_chest(self):
        p = _make_player()
        _equip(p, "Iron Greaves", EquipSlot.LEGS, bonus=3)
        curse = Curse("It's Taking Over!", effect_id="its_taking_over", strength_bonus=0)
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert p.leg_armor == []
        assert any("Iron Greaves" in msg for msg in log)


# ===================================================================
# Get Rekt — block helmet or chest slot
# ===================================================================

class TestGetRekt:

    def test_discards_highest_str_item(self):
        p = _make_player()
        helm = _equip(p, "Iron Helm", EquipSlot.HELMET, bonus=3)
        boot = _equip(p, "Steel Boots", EquipSlot.LEGS, bonus=5)
        curse = Curse("Get Rekt!", effect_id="get_rekt")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        # Steel Boots (+5) is highest — should be discarded
        assert boot not in p.leg_armor
        assert helm in p.helmets
        assert any("Steel Boots" in msg and "Discarded" in msg for msg in log)

    def test_no_items_logs_message(self):
        p = _make_player()
        curse = Curse("Get Rekt!", effect_id="get_rekt")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert any("no eligible" in msg for msg in log)

    def test_locked_items_skipped(self):
        p = _make_player()
        locked = Item("Locked Boots", EquipSlot.LEGS, strength_bonus=10,
                      locked_by_curse_id="some_curse")
        anchor = Curse("some_curse", effect_id="some_curse")
        p.leg_armor.append(locked)
        p.curses.append(anchor)
        helm = _equip(p, "Helm", EquipSlot.HELMET, bonus=2)
        curse = Curse("Get Rekt!", effect_id="get_rekt")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        # Locked boots should be skipped; unlocked helm discarded
        assert locked in p.leg_armor
        assert helm not in p.helmets

    def test_blocked_helmet_slot_reduces_helmet_capacity(self):
        p = _make_player()
        curse = Curse("Get Rekt!", effect_id="get_rekt")
        curse.helmet_slot_bonus = -1
        p.curses.append(curse)
        fx.refresh_tokens(p)
        # Default helmet slot is 1; -1 means 0 = can't equip helmet
        assert p.helmet_slots == 0


# ===================================================================
# Can't Stop the Music — force locked Dancing Shoes
# ===================================================================

class TestCantStopMusic:

    def test_dancing_shoes_added_to_leg_armor(self):
        p = _make_player()
        curse = Curse("Can't Stop the Music!", effect_id="cant_stop_music")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.leg_armor) == 1
        shoes = p.leg_armor[0]
        assert shoes.name == "Dancing Shoes"
        assert shoes.strength_bonus == 1
        assert shoes.locked_by_curse_id == "cant_stop_music"

    def test_existing_leg_armor_discarded(self):
        p = _make_player()
        _equip(p, "Rubber Boots", EquipSlot.LEGS, bonus=2)
        curse = Curse("Can't Stop the Music!", effect_id="cant_stop_music")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert len(p.leg_armor) == 1
        assert p.leg_armor[0].name == "Dancing Shoes"
        assert any("Rubber Boots" in msg for msg in log)

    def test_dancing_shoes_locked_by_curse(self):
        p = _make_player()
        curse = Curse("Can't Stop the Music!", effect_id="cant_stop_music")
        p.curses.append(curse)
        fx.on_curse_gained(p, curse, [])
        shoes = p.leg_armor[0]
        assert p.unequip(shoes) is False  # locked while curse active

    def test_dancing_shoes_strength_counts(self):
        p = _make_player()
        curse = Curse("Can't Stop the Music!", effect_id="cant_stop_music")
        p.curses.append(curse)
        fx.on_curse_gained(p, curse, [])
        fx.refresh_tokens(p)
        # base_strength=1 + Dancing Shoes +1 = 2 (curse has no strength_bonus)
        assert p.total_strength == 2


# ===================================================================
# Drank Blood — force locked Bloody Stump
# ===================================================================

class TestDrankBlood:

    def test_stump_added_when_no_weapons(self):
        p = _make_player()
        curse = Curse("He Drank Your Blood. Then Ate Your Arm.", effect_id="drank_blood")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert any(w.name == "Bloody Stump" for w in p.weapons)

    def test_stump_replaces_one_handed_weapon(self):
        p = _make_player()
        _equip(p, "Short Sword", EquipSlot.WEAPON, bonus=3)
        curse = Curse("He Drank Your Blood. Then Ate Your Arm.", effect_id="drank_blood")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert not any(w.name == "Short Sword" for w in p.weapons)
        assert any(w.name == "Bloody Stump" for w in p.weapons)

    def test_two_handed_weapon_always_discarded(self):
        p = _make_player()
        sword = Item("Great Sword", EquipSlot.WEAPON, strength_bonus=5, hands=2)
        p.weapons.append(sword)
        curse = Curse("He Drank Your Blood. Then Ate Your Arm.", effect_id="drank_blood")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert not any(w.name == "Great Sword" for w in p.weapons)
        assert any(w.name == "Bloody Stump" for w in p.weapons)
        assert any("2H" in msg for msg in log)

    def test_stump_is_locked(self):
        p = _make_player()
        curse = Curse("He Drank Your Blood. Then Ate Your Arm.", effect_id="drank_blood")
        p.curses.append(curse)
        fx.on_curse_gained(p, curse, [])
        stump = next(w for w in p.weapons if w.name == "Bloody Stump")
        assert p.unequip(stump) is False

    def test_stump_strength_bonus_is_negative_three(self):
        p = _make_player()
        curse = Curse("He Drank Your Blood. Then Ate Your Arm.", effect_id="drank_blood",
                      strength_bonus=-5)
        p.curses.append(curse)
        fx.on_curse_gained(p, curse, [])
        stump = next(w for w in p.weapons if w.name == "Bloody Stump")
        assert stump.strength_bonus == -3

    def test_decide_fn_selects_which_weapon_to_replace(self):
        p = _make_player()
        sword1 = Item("First Sword", EquipSlot.WEAPON, strength_bonus=3, hands=1)
        sword2 = Item("Second Sword", EquipSlot.WEAPON, strength_bonus=4, hands=1)
        p.weapons.extend([sword1, sword2])
        curse = Curse("He Drank Your Blood. Then Ate Your Arm.", effect_id="drank_blood")
        p.curses.append(curse)
        log: list[str] = []
        # decide_fn True = replace first weapon
        fx.on_curse_gained(p, curse, log, decide_fn=lambda prompt, log: True)
        assert not any(w.name == "First Sword" for w in p.weapons)
        assert any(w.name == "Second Sword" for w in p.weapons)


# ===================================================================
# Kneel — Werbler gets +10 Str per curse (tested via encounter)
# ===================================================================

class TestKneelEffect:

    def test_kneel_on_gain_logs_warning(self):
        p = _make_player()
        curse = Curse("KNEEL!", effect_id="kneel")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert any("KNEEL" in msg or "Werbler" in msg for msg in log)

    def test_kneel_in_encounter_werbler_boosts_strength(self):
        from werblers_engine import encounters as enc
        from werblers_engine.deck import Deck
        p = _make_player()
        p.strength = 100  # guarantee win if Werbler is normal
        curse = Curse("KNEEL!", effect_id="kneel")
        p.curses.append(curse)
        # Force a scenario where Werbler boost is logged
        curse_deck = Deck([], seed=42, auto_reshuffle=False)
        werbler = Monster("The Very Cool Werbler Test", strength=5, level=3)
        log: list[str] = []
        enc.encounter_werbler(p, werbler, curse_deck, log)
        assert any("KNEEL" in msg and "+10" in msg for msg in log)


# ===================================================================
# So Lethargic — -1 Str per 3/4 played (tested via game.py)
# ===================================================================

class TestSoLethargic:

    def test_so_lethargic_decrements_on_3_or_4(self):
        from werblers_engine.game import Game
        from werblers_engine.deck import Deck
        game = Game(num_players=1, seed=42)
        p = game.player
        curse = Curse("So\u2026 Lethargic\u2026", effect_id="so_lethargic", strength_bonus=0)
        p.curses.append(curse)
        # Force a 3 into the movement hand
        p.movement_hand = [3]
        game.play_turn(card_index=0)
        assert curse.strength_bonus == -1

    def test_so_lethargic_no_change_on_1_or_2(self):
        from werblers_engine.game import Game
        game = Game(num_players=1, seed=42)
        p = game.player
        curse = Curse("So\u2026 Lethargic\u2026", effect_id="so_lethargic", strength_bonus=0)
        p.curses.append(curse)
        p.movement_hand = [1]
        game.play_turn(card_index=0)
        assert curse.strength_bonus == 0

    def test_so_lethargic_accumulates(self):
        from werblers_engine.game import Game
        game = Game(num_players=1, seed=42)
        p = game.player
        curse = Curse("So\u2026 Lethargic\u2026", effect_id="so_lethargic", strength_bonus=0)
        p.curses.append(curse)
        p.movement_hand = [4, 3]
        game.play_turn(card_index=0)  # plays 4
        p.movement_hand.insert(0, 3)
        game.play_turn(card_index=0)  # plays 3
        assert curse.strength_bonus == -2


# ===================================================================
# Bad Trip — random card selection
# ===================================================================

class TestBadTrip:

    def test_bad_trip_plays_a_card_from_hand(self):
        from werblers_engine.game import Game
        import random
        game = Game(num_players=1, seed=0)
        p = game.player
        curse = Curse("Bad Trip", effect_id="bad_trip")
        p.curses.append(curse)
        p.movement_hand = [1, 2, 3, 4, 5, 6]
        original_len = len(p.movement_hand)
        random.seed(0)
        result = game.play_turn(card_index=0)
        # One card was consumed from the hand (bad_trip picks randomly)
        assert len(p.movement_hand) == original_len - 1


# ===================================================================
# Walk of Shame — curse immediately removed on gain
# ===================================================================

class TestWalkOfShame:

    def test_walk_of_shame_stays_in_curse_list(self):
        """The curse remains (counts toward curse total) but has no other effect."""
        p = _make_player()
        curse = Curse("Wait, You Lost to THIS?", effect_id="walk_of_shame")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log)
        assert curse in p.curses
        assert any("nothing happens" in msg for msg in log)

    def test_walk_of_shame_not_in_curse_pool(self):
        pool_ids = {c.effect_id for c in C.CURSE_POOL}
        assert "walk_of_shame" not in pool_ids


# ===================================================================
# Enslaved — give one item to an opponent
# ===================================================================

class TestEnslaved:

    def test_enslaved_transfers_item_to_other_player(self):
        p1 = Player(player_id=0, name="Player 1")
        p2 = Player(player_id=1, name="Player 2")
        item = _equip(p1, "Iron Helm", EquipSlot.HELMET)
        curse = Curse("Enslaved!", effect_id="enslaved")
        p1.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p1, curse, log, other_players=[p2])
        # Item removed from player 1
        assert item not in p1.helmets
        # Item given to player 2 (equipped or in pack)
        all_p2_items = p2.helmets + p2.chest_armor + p2.leg_armor + p2.weapons + p2.pack
        assert item in all_p2_items

    def test_enslaved_no_other_players_skips(self):
        p = _make_player()
        _equip(p, "Iron Helm", EquipSlot.HELMET)
        curse = Curse("Enslaved!", effect_id="enslaved")
        p.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p, curse, log, other_players=None)
        assert any("skipped" in msg for msg in log)

    def test_enslaved_no_items_skips(self):
        p1 = Player(player_id=0, name="Player 1")
        p2 = Player(player_id=1, name="Player 2")
        curse = Curse("Enslaved!", effect_id="enslaved")
        p1.curses.append(curse)
        log: list[str] = []
        fx.on_curse_gained(p1, curse, log, other_players=[p2])
        assert any("no more items" in msg for msg in log)

    def test_enslaved_does_not_give_locked_items(self):
        p1 = Player(player_id=0, name="Player 1")
        p2 = Player(player_id=1, name="Player 2")
        # Only item is locked Dancing Shoes
        music_curse = Curse("Can't Stop the Music!", effect_id="cant_stop_music")
        p1.curses.append(music_curse)
        shoes = Item("Dancing Shoes", EquipSlot.LEGS, strength_bonus=1,
                     locked_by_curse_id="cant_stop_music")
        p1.leg_armor.append(shoes)
        enslaved_curse = Curse("Enslaved!", effect_id="enslaved")
        p1.curses.append(enslaved_curse)
        log: list[str] = []
        fx.on_curse_gained(p1, enslaved_curse, log, other_players=[p2])
        # Dancing Shoes should still be on p1 (locked)
        assert shoes in p1.leg_armor


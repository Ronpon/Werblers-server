"""Tests for combat resolution."""

from werblers_engine.combat import resolve_combat
from werblers_engine.types import CombatResult, Monster
from werblers_engine.player import Player


def test_player_wins():
    player = Player(base_strength=5)
    monster = Monster("Weak Slime", strength=3, level=1)
    assert resolve_combat(player, monster) == CombatResult.WIN


def test_player_loses():
    player = Player(base_strength=1)
    monster = Monster("Strong Troll", strength=10, level=2)
    assert resolve_combat(player, monster) == CombatResult.LOSE


def test_tie():
    player = Player(base_strength=5)
    monster = Monster("Equal Foe", strength=5, level=1)
    assert resolve_combat(player, monster) == CombatResult.TIE


def test_equipment_affects_strength():
    from werblers_engine.types import Item, EquipSlot

    player = Player(base_strength=1)
    sword = Item("Big Sword", EquipSlot.WEAPON, strength_bonus=4)
    player.equip(sword)
    monster = Monster("Orc", strength=4, level=1)
    assert resolve_combat(player, monster) == CombatResult.WIN

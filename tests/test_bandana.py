from werblers_engine.player import Player
from werblers_engine.types import Item, EquipSlot

def test_sweet_bandana_equip():
    bandana = Item("Sweet bandana", EquipSlot.HELMET, strength_bonus=2)
    player = Player()
    assert player.can_equip(bandana)
    equipped = player.equip(bandana)
    assert equipped
    assert bandana in player.helmets
    assert player.total_strength == 3  # base 1 + 2 from bandana
"""Tests for mystery event resolution.

Ensure each event type resolves without errors and the game can continue
(turn advances or a valid follow-up phase is returned).
"""
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from werblers_engine.player import Player
from werblers_engine.types import Item, EquipSlot, Monster, Trait
from werblers_engine.deck import Deck
from werblers_engine import mystery as mys


def _make_player(name="Hero", items=2, equip=1):
    """Create a player with some pack items and optionally an equipped item."""
    p = Player(1, name)
    for i in range(items):
        p.pack.append(Item(f"PackItem{i}", EquipSlot.WEAPON, i + 1))
    for i in range(equip):
        it = Item(f"EquipItem{i}", EquipSlot.HELMET, i + 2)
        p.equip(it)
    return p


def _make_decks():
    """Create item / monster / trait decks with a few entries."""
    items = [Item(f"Prize{i}", EquipSlot.CHEST, i + 3) for i in range(10)]
    monsters = [Monster(f"Mon{i}", strength=i + 2, level=1) for i in range(5)]
    traits = [Trait(f"Trait{i}", effect_id=f"trait_{i}") for i in range(5)]
    return {1: Deck(list(items)), 2: Deck(list(items)), 3: Deck(list(items))}, \
           {1: Deck(list(monsters)), 2: Deck(list(monsters)), 3: Deck(list(monsters))}, \
           Deck(list(traits))


# ------------------------------------------------------------------ helpers
def _assert_valid_result(result, label):
    assert isinstance(result, dict), f"{label}: result should be dict, got {type(result)}"
    pt = result.get("prize_type")
    assert pt is not None, f"{label}: result missing prize_type"
    assert pt != "error", f"{label}: got error result — {result}"
    print(f"  OK  {label}: prize_type={pt}")


# ------------------------------------------------------------------ tests

def test_mystery_box_valid_wager():
    """Mystery box: wagering a valid pack item should resolve."""
    p = _make_player()
    item_decks, monster_decks, trait_deck = _make_decks()
    log = []
    result = mys.resolve_mystery_box(p, 1, 0, item_decks, monster_decks, trait_deck, log)
    _assert_valid_result(result, "mystery_box_valid_wager")
    assert len(p.pack) < 2, "wagered item should be removed from pack"


def test_mystery_box_invalid_wager():
    """Mystery box: invalid wager index returns error."""
    p = _make_player(items=0)
    item_decks, monster_decks, trait_deck = _make_decks()
    log = []
    result = mys.resolve_mystery_box(p, 1, -1, item_decks, monster_decks, trait_deck, log)
    assert result.get("prize_type") == "error"
    print("  OK  mystery_box_invalid_wager: correctly returned error")


def test_mystery_box_equipped_wager():
    """Mystery box: wagering an equipped item (beyond pack+consumables+monsters)."""
    p = _make_player(items=1, equip=1)
    item_decks, monster_decks, trait_deck = _make_decks()
    log = []
    # Pack has 1 item (idx 0), equipped has 1 item (idx 1)
    wager_idx = 1  # the equipped item
    result = mys.resolve_mystery_box(p, 1, wager_idx, item_decks, monster_decks, trait_deck, log)
    _assert_valid_result(result, "mystery_box_equipped_wager")
    assert len(p.helmets) == 0, "equipped item should be removed after wager"
    assert "equipped" in log[-2].lower() or "wagered" in log[-2].lower(), f"log should mention wagered item: {log}"


def test_mystery_box_only_equipped():
    """Mystery box: player has ONLY equipped items — should still work."""
    p = _make_player(items=0, equip=2)
    item_decks, monster_decks, trait_deck = _make_decks()
    log = []
    result = mys.resolve_mystery_box(p, 1, 0, item_decks, monster_decks, trait_deck, log)
    _assert_valid_result(result, "mystery_box_only_equipped")
    assert len(p.helmets) < 2, "one equipped item should be removed"


def test_the_wheel():
    """The Wheel: should always resolve with a prize."""
    p = _make_player()
    item_decks, monster_decks, trait_deck = _make_decks()
    for seed in range(20):
        log = []
        i_d, m_d, t_d = _make_decks()
        result = mys.resolve_the_wheel(p, 1, i_d, m_d, t_d, log, rng=random.Random(seed))
        _assert_valid_result(result, f"the_wheel_seed{seed}")


def test_the_smith_trade():
    """The Smith (tier 1-2): trade 3 items for a higher-tier item."""
    p = _make_player(items=4)
    item_decks, _, _ = _make_decks()
    log = []
    result = mys.resolve_the_smith(p, 1, item_decks, [0, 1, 2], -1, log)
    _assert_valid_result(result, "the_smith_trade")
    assert len(p.pack) <= 2, f"should have removed 3 items, pack has {len(p.pack)}"


def test_the_smith_trade_with_equipped():
    """The Smith (tier 1-2): trade a mix of pack and equipped items."""
    p = _make_player(items=2, equip=1)
    item_decks, _, _ = _make_decks()
    log = []
    # Pack indices 0,1; equipped index 2
    result = mys.resolve_the_smith(p, 1, item_decks, [0, 1, 2], -1, log)
    _assert_valid_result(result, "the_smith_trade_with_equipped")
    assert len(p.pack) == 0, "both pack items should be gone"
    assert len(p.helmets) == 0, "equipped item should be gone"


def test_the_smith_enhance():
    """The Smith (tier 3): trade 3 pack items and enhance an equipped item."""
    p = _make_player(items=3, equip=1)
    item_decks, _, _ = _make_decks()
    log = []
    result = mys.resolve_the_smith(p, 3, item_decks, [0, 1, 2], 0, log)
    _assert_valid_result(result, "the_smith_enhance")


def test_bandits():
    """Bandits: should steal an equipped item."""
    p = _make_player(items=0, equip=1)
    log = []
    result = mys.resolve_bandits(p, log)
    _assert_valid_result(result, "bandits")


def test_bandits_no_equips():
    """Bandits: with no equipped items, should return skip/nothing."""
    p = _make_player(items=2, equip=0)
    log = []
    result = mys.resolve_bandits(p, log)
    _assert_valid_result(result, "bandits_no_equips")


def test_thief():
    """Thief: should steal pack items."""
    p = _make_player(items=3)
    log = []
    result = mys.resolve_thief(p, log)
    _assert_valid_result(result, "thief")
    assert len(p.pack) == 0, "thief should steal all pack items"


def test_thief_empty_pack():
    """Thief: with no pack items, returns skip."""
    p = _make_player(items=0, equip=0)
    log = []
    result = mys.resolve_thief(p, log)
    _assert_valid_result(result, "thief_empty_pack")


def test_beggar_give():
    """Beggar: give an item, should track gifts."""
    p = _make_player(items=2, equip=1)
    item_decks, _, _ = _make_decks()
    log = []
    # Give first item (pack index 0)
    result = mys.resolve_beggar(p, 1, item_decks, 0, log)
    _assert_valid_result(result, "beggar_give_1")
    assert result["prize_type"] == "beggar_thank", f"expected beggar_thank, got {result['prize_type']}"
    assert getattr(p, "_beggar_gifts", 0) == 1


def test_beggar_three_gifts_fairy_king():
    """Beggar: after 3 gifts, should trigger fairy king reveal."""
    p = _make_player(items=3, equip=1)
    item_decks, _, _ = _make_decks()
    for i in range(3):
        log = []
        i_d, _, _ = _make_decks()
        result = mys.resolve_beggar(p, 1, i_d, 0, log)
        _assert_valid_result(result, f"beggar_give_{i+1}")
        if i < 2:
            assert result["prize_type"] == "beggar_thank"
        else:
            assert result["prize_type"] == "fairy_king_reveal"
            assert "reward_items" in result
            assert len(result["reward_items"]) > 0
    assert getattr(p, "_beggar_completed", False) is True


def test_beggar_completed_skip():
    """Beggar: once completed, should skip."""
    p = _make_player(items=2)
    p._beggar_completed = True
    item_decks, _, _ = _make_decks()
    log = []
    result = mys.resolve_beggar(p, 1, item_decks, 0, log)
    _assert_valid_result(result, "beggar_completed_skip")
    assert result["prize_type"] == "skip"


def test_roll_mystery_event_no_fairy_king():
    """Roll mystery event should never return fairy_king directly."""
    seen_ids = set()
    for pos in range(1, 100):
        ev = mys.roll_mystery_event(pos)
        seen_ids.add(ev.event_id)
        assert ev.event_id != "fairy_king", f"fairy_king should NOT be in the event pool (pos={pos})"
    print(f"  OK  roll_mystery_event: seen events = {seen_ids}")
    # Verify beggar IS in the pool
    # (rare, so may not appear in 100 rolls — that's OK)


def test_all_events_have_descriptions():
    """Every event in _EVENT_TABLE should have a description."""
    for event_id, name, rarity, img_name in mys._EVENT_TABLE:
        assert event_id in mys._EVENT_DESCRIPTIONS, f"Missing description for {event_id}"
    print("  OK  all events have descriptions")


# ------------------------------------------------------------------ main

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed:
        sys.exit(1)

"""Mystery Square event system.

Each Mystery Square triggers a randomly chosen event with weighted
probabilities.  Events vary by tier (determined by the player's current
board position).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .types import Item, Monster, Trait, Curse, Minion
from .player import Player
from .deck import Deck
from . import content as C
from . import effects as _fx


# ---------------------------------------------------------------------------
# Event definitions
# ---------------------------------------------------------------------------

# Rarity weights — relative probability of each rarity band.
# common=50, uncommon=25, rare=15, very_rare=10  (total 100)

@dataclass
class MysteryEvent:
    """Describes a mystery event to present to the player."""
    event_id: str          # e.g. "mystery_box", "the_wheel", "the_smith"
    name: str              # display name
    tier: int              # 1/2/3 derived from board position
    description: str = ""  # flavour text shown on the modal


# Event catalogue with rarity bands
_EVENT_TABLE: list[tuple[str, str, str]] = [
    # (event_id, display_name, rarity)
    ("mystery_box",  "Mystery Box",  "common"),
    ("the_wheel",    "The Wheel",    "common"),
    ("the_smith",    "The Smith",    "uncommon"),
    ("bandits",      "Bandits",      "uncommon"),
    ("thief",        "Thief",        "rare"),
    ("fairy_king",   "Fairy King",   "rare"),
]

_RARITY_WEIGHTS = {
    "common":    50,
    "uncommon":  25,
    "rare":      15,
    "very_rare": 10,
}


def _get_tier(position: int) -> int:
    if position <= 30:
        return 1
    if position <= 60:
        return 2
    return 3


# ---------------------------------------------------------------------------
# Roll a random event
# ---------------------------------------------------------------------------

def roll_mystery_event(position: int, rng: random.Random | None = None) -> MysteryEvent:
    """Select a random mystery event weighted by rarity."""
    if rng is None:
        rng = random.Random()

    tier = _get_tier(position)
    ids = [e[0] for e in _EVENT_TABLE]
    names = [e[1] for e in _EVENT_TABLE]
    rarities = [e[2] for e in _EVENT_TABLE]
    weights = [_RARITY_WEIGHTS[r] for r in rarities]

    idx = rng.choices(range(len(ids)), weights=weights, k=1)[0]
    desc = _EVENT_DESCRIPTIONS.get(ids[idx], "")
    return MysteryEvent(
        event_id=ids[idx],
        name=names[idx],
        tier=tier,
        description=desc,
    )


_EVENT_DESCRIPTIONS = {
    "mystery_box":  "A mysterious chest appears! Wager an item from your pack for a chance at a prize.",
    "the_wheel":    "A great wheel materialises before you! Give it a spin for a free prize!",
    "the_smith":    "A skilled blacksmith offers their services.",
    "bandits":      "Bandits leap from the shadows!",
    "thief":        "A thief slinks out of the darkness!",
    "fairy_king":   "The Fairy King appears and asks for a gift.",
}


# ---------------------------------------------------------------------------
# Prize pool
# ---------------------------------------------------------------------------

# Prize types returned by _roll_prize:
#   "item"    → (tier_item, None)        — draw from item deck of given tier
#   "monster" → (None, monster_level)     — fight a monster (same or +1 tier)
#   "trait"   → (dead_monster_trait, None)— gain a dead monster's trait
#   "nothing" → (None, None)             — no prize

@dataclass
class Prize:
    prize_type: str       # "item", "monster", "monster_up", "trait", "nothing"
    tier: int = 1         # item tier for "item" prizes
    label: str = ""       # human-readable description


def _roll_prize(tier: int, rng: random.Random) -> Prize:
    """Roll a random prize from the mystery prize table."""
    # Weighted table: (prize_type, extra_tier_offset, label, weight)
    table = [
        ("item",       0, f"Tier {tier} item",             50),   # common
        ("monster",    0, f"Tier {tier} monster",           15),   # uncommon
        ("monster_up", 1, f"Tier {min(tier+1, 3)} monster", 10),  # rare
        ("nothing",    0, "Nothing!",                       15),   # rare
        ("trait",      0, "Dead monster's trait",            10),  # very rare
    ]
    types = [t[0] for t in table]
    weights = [t[3] for t in table]
    labels = [t[2] for t in table]

    idx = rng.choices(range(len(types)), weights=weights, k=1)[0]
    prize_tier = tier + table[idx][1]
    if prize_tier > 3:
        prize_tier = 3
    return Prize(prize_type=types[idx], tier=prize_tier, label=labels[idx])


# ---------------------------------------------------------------------------
# Event resolution helpers
# ---------------------------------------------------------------------------

def resolve_mystery_box(
    player: Player,
    tier: int,
    wager_pack_index: int,
    item_decks: dict[int, Deck],
    monster_decks: dict[int, Deck],
    trait_deck: Deck,
    log: list[str],
    rng: random.Random | None = None,
) -> dict:
    """Mystery Box: player wagers a pack item for a chance at a prize.

    Returns a result dict with keys:
      prize_type, item (if any), monster (if any), trait (if any), label
    """
    if rng is None:
        rng = random.Random()

    # Wager the item
    np = len(player.pack)
    nc = len(player.consumables)
    nm = len(player.captured_monsters)
    total = np + nc + nm
    if wager_pack_index < 0 or wager_pack_index >= total:
        log.append("Mystery Box: invalid wager — no item selected.")
        return {"prize_type": "error"}

    if wager_pack_index < np:
        wagered = player.pack.pop(wager_pack_index)
        log.append(f"Mystery Box: wagered {wagered.name}.")
    elif wager_pack_index < np + nc:
        wagered = player.consumables.pop(wager_pack_index - np)
        log.append(f"Mystery Box: wagered {wagered.name} (consumable).")
    else:
        wagered = player.captured_monsters.pop(wager_pack_index - np - nc)
        log.append(f"Mystery Box: wagered {wagered.name} (captured monster).")

    prize = _roll_prize(tier, rng)
    return _materialise_prize(prize, tier, player, item_decks, monster_decks, trait_deck, log, rng)


def resolve_the_wheel(
    player: Player,
    tier: int,
    item_decks: dict[int, Deck],
    monster_decks: dict[int, Deck],
    trait_deck: Deck,
    log: list[str],
    rng: random.Random | None = None,
) -> dict:
    """The Wheel: free spin — no wager required."""
    if rng is None:
        rng = random.Random()
    log.append("The Wheel: spinning!")
    prize = _roll_prize(tier, rng)
    return _materialise_prize(prize, tier, player, item_decks, monster_decks, trait_deck, log, rng)


def resolve_the_smith(
    player: Player,
    tier: int,
    item_decks: dict[int, Deck],
    wager_indices: list[int],
    chosen_equip_index: int,
    log: list[str],
) -> dict:
    """The Smith: trade 3 pack items for one item of the next tier.

    At Tier 3, instead choose an equipped item to receive +3 Str.
    ``wager_indices`` are unified pack indices (sorted descending for safe pop).
    ``chosen_equip_index`` is the index into the player's all-equipped list
    (only used at Tier 3).
    """
    if tier < 3:
        # Trade 3 items from pack for 1 item of tier+1
        if len(wager_indices) < 3:
            log.append("The Smith: need 3 items to trade.")
            return {"prize_type": "error"}
        names = []
        for idx in sorted(wager_indices, reverse=True):
            name = player.evict_pack_slot(idx)
            if name:
                names.append(name)
        log.append(f"The Smith: traded {', '.join(names)}.")
        next_tier = min(tier + 1, 3)
        reward = item_decks[next_tier].draw()
        if reward:
            log.append(f"The Smith: received {reward.name} (Tier {next_tier})!")
            return {"prize_type": "item", "item": reward, "label": f"Tier {next_tier} item"}
        else:
            log.append("The Smith: item deck empty — no reward.")
            return {"prize_type": "nothing", "label": "Deck empty"}
    else:
        # Tier 3: add +3 Str to a chosen equipped item
        all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
        if not all_equipped:
            log.append("The Smith: no equipped items to enhance.")
            return {"prize_type": "nothing", "label": "No items"}
        if chosen_equip_index < 0 or chosen_equip_index >= len(all_equipped):
            log.append("The Smith: invalid item selection.")
            return {"prize_type": "error"}
        item = all_equipped[chosen_equip_index]
        item.strength_bonus += 3
        log.append(f"The Smith: enhanced {item.name} by +3 Str (now +{item.strength_bonus})!")
        return {"prize_type": "smith_enhance", "item_name": item.name, "label": f"+3 Str to {item.name}"}


def resolve_bandits(
    player: Player,
    log: list[str],
) -> dict:
    """Bandits: forced discard of 1 random equipped item. Skip if nothing equipped."""
    all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    if not all_equipped:
        log.append("Bandits: you have nothing equipped — the bandits leave you alone!")
        return {"prize_type": "skip", "label": "Bandits leave you alone"}

    rng = random.Random()
    victim = rng.choice(all_equipped)
    player.unequip(victim)
    log.append(f"Bandits: stole your {victim.name}!")
    return {"prize_type": "stolen", "item_name": victim.name, "label": f"Lost {victim.name}"}


def resolve_thief(
    player: Player,
    log: list[str],
) -> dict:
    """Thief: lose all pack items. Skip if pack is empty."""
    pack_count = len(player.pack) + len(player.consumables) + len(player.captured_monsters)
    if pack_count == 0:
        log.append("Thief: your pack is empty — the thief slinks away!")
        return {"prize_type": "skip", "label": "Thief leaves you alone"}

    names = [i.name for i in player.pack] + [c.name for c in player.consumables] + [m.name for m in player.captured_monsters]
    player.pack.clear()
    player.consumables.clear()
    player.captured_monsters.clear()
    log.append(f"Thief: stole everything from your pack! Lost: {', '.join(names)}")
    return {"prize_type": "stolen", "items": names, "label": "Lost all pack items"}


def resolve_fairy_king(
    player: Player,
    tier: int,
    item_decks: dict[int, Deck],
    give_pack_index: int,
    log: list[str],
) -> dict:
    """Fairy King: give an item. Track per-player counter. 3rd gift → Tier 3 item reward.

    The counter is stored as a player attribute ``_fairy_king_gifts``.
    """
    gifts_so_far = getattr(player, "_fairy_king_gifts", 0)
    np = len(player.pack)
    nc = len(player.consumables)
    nm = len(player.captured_monsters)
    total = np + nc + nm
    # Check if player has anything to give
    all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    total_all = total + len(all_equipped)
    if total_all == 0:
        log.append("Fairy King: you have nothing to give — the Fairy King bows and departs.")
        return {"prize_type": "skip", "label": "Nothing to give"}

    if give_pack_index < 0 or give_pack_index >= total + len(all_equipped):
        log.append("Fairy King: invalid item selection.")
        return {"prize_type": "error"}

    # Give from pack first, then equipped
    if give_pack_index < total:
        name = player.evict_pack_slot(give_pack_index)
        log.append(f"Fairy King: you gave {name}.")
    else:
        equip_idx = give_pack_index - total
        item = all_equipped[equip_idx]
        player.unequip(item)
        log.append(f"Fairy King: you gave {item.name} (equipped).")
        name = item.name

    gifts_so_far += 1
    player._fairy_king_gifts = gifts_so_far  # type: ignore[attr-defined]

    if gifts_so_far >= 3:
        # Reset counter and grant Tier 3 item
        player._fairy_king_gifts = 0  # type: ignore[attr-defined]
        reward = item_decks[3].draw()
        if reward:
            log.append(f"Fairy King: impressed by your generosity! Received {reward.name} (Tier 3)!")
            return {"prize_type": "item", "item": reward, "label": f"Tier 3 reward: {reward.name}", "fairy_king_reward": True}
        else:
            log.append("Fairy King: impressed, but the deck is empty — no reward.")
            return {"prize_type": "nothing", "label": "Deck empty", "fairy_king_reward": True}
    else:
        remaining = 3 - gifts_so_far
        log.append(f"Fairy King: {remaining} more gift(s) until a reward!")
        return {"prize_type": "gift_accepted", "gifts_remaining": remaining, "label": f"Gift accepted ({remaining} more to go)"}


# ---------------------------------------------------------------------------
# Prize materialisation
# ---------------------------------------------------------------------------

def _materialise_prize(
    prize: Prize,
    tier: int,
    player: Player,
    item_decks: dict[int, Deck],
    monster_decks: dict[int, Deck],
    trait_deck: Deck,
    log: list[str],
    rng: random.Random,
) -> dict:
    """Turn an abstract Prize into a concrete result dict."""
    if prize.prize_type == "item":
        item = item_decks[prize.tier].draw()
        if item:
            log.append(f"  Prize: {item.name} (Tier {prize.tier} item)!")
            return {"prize_type": "item", "item": item, "label": prize.label}
        else:
            log.append("  Prize: item deck empty — nothing.")
            return {"prize_type": "nothing", "label": "Deck empty"}

    elif prize.prize_type in ("monster", "monster_up"):
        m_tier = prize.tier
        monster = monster_decks[m_tier].draw()
        if monster:
            log.append(f"  Prize: {monster.name} (Tier {m_tier} monster) — prepare to fight!")
            return {"prize_type": "monster", "monster": monster, "tier": m_tier, "label": prize.label}
        else:
            log.append("  Prize: monster deck empty — lucky escape!")
            return {"prize_type": "nothing", "label": "Monster deck empty"}

    elif prize.prize_type == "trait":
        # Draw a random dead monster and give its trait
        all_monsters = []
        for t in (1, 2, 3):
            deck = monster_decks.get(t)
            if deck:
                all_monsters.extend(deck.peek_all())
        monsters_with_traits = [m for m in all_monsters if m.trait_name]
        if monsters_with_traits:
            chosen = rng.choice(monsters_with_traits)
            trait = C.trait_for_monster(chosen)
            if trait:
                player.traits.append(trait)
                log.append(f"  Prize: gained trait '{trait.name}' from {chosen.name}!")
                trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
                player.pending_trait_items.extend(trait_items)
                player.pending_trait_minions.extend(trait_minions)
                _fx.refresh_tokens(player)
                return {"prize_type": "trait", "trait": trait, "label": f"Trait: {trait.name}"}
        # Fallback: draw from trait deck
        trait = trait_deck.draw()
        if trait:
            player.traits.append(trait)
            log.append(f"  Prize: gained random trait '{trait.name}'!")
            trait_items, trait_minions = _fx.on_trait_gained(player, trait, log)
            player.pending_trait_items.extend(trait_items)
            player.pending_trait_minions.extend(trait_minions)
            _fx.refresh_tokens(player)
            return {"prize_type": "trait", "trait": trait, "label": f"Trait: {trait.name}"}
        log.append("  Prize: no traits available — nothing.")
        return {"prize_type": "nothing", "label": "No traits available"}

    else:  # "nothing"
        log.append("  Prize: nothing! Better luck next time.")
        return {"prize_type": "nothing", "label": "Nothing"}

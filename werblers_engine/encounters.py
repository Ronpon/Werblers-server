"""Encounter resolution for each tile type --- RULES.md §7."""

from __future__ import annotations

from typing import Callable, Optional

from .types import (
    CombatResult,
    Consumable,
    GameStatus,
    TileType,
    Trait,
    Curse,
    Item,
    Monster,
)
from .player import Player
from .combat import resolve_combat
from .deck import Deck
from . import content as C
from . import effects as _fx


def _pick_random_trait(trait_deck: Deck[Trait]) -> Optional[Trait]:
    return trait_deck.draw()


def _pick_random_curse(curse_deck: Deck[Curse]) -> Optional[Curse]:
    return curse_deck.draw()


def _apply_brunhilde_combat_loss(player: Player, log: list[str]) -> None:
    """Brunhilde: Skimpy Armour --- destroy chest armour on combat loss."""
    if player.hero and player.hero.has_skimpy_armour and player.chest_armor:
        destroyed = player.chest_armor.pop(0)
        _fx.refresh_tokens(player)
        log.append(
            f"  Skimpy Armour: {destroyed.name} was shredded in defeat and discarded!"
        )


# ------------------------------------------------------------------
# Central curse-application guard
# ------------------------------------------------------------------

_FOOTGEAR_CURSE_IDS = {"it_got_in", "need_a_place", "cant_stop_music"}
_WEAPON_DISCARD_CURSE_IDS = {"rust_spreading"}


def _apply_curse(
    player: Player,
    curse: Curse,
    monster: Optional[Monster],
    log: list[str],
    decide_fn: Optional[Callable] = None,
    other_players: Optional[list] = None,
    select_fn: Optional[Callable] = None,
) -> bool:
    """Apply a curse to the player, checking immunity guards first.

    Returns True if the curse was actually applied, False if it was blocked.
    """
    # Phallic Dexterity: block footgear curses
    if curse.effect_id in _FOOTGEAR_CURSE_IDS:
        if any(t.effect_id == "phallic_dexterity" for t in player.traits):
            log.append(f"  Phallic Dexterity: {curse.name} blocked! (footgear immunity)")
            return False

    # Rust Immunity: block weapon-discard curses
    if curse.effect_id in _WEAPON_DISCARD_CURSE_IDS:
        if any(t.effect_id == "rust_immunity" for t in player.traits):
            log.append(f"  Rust Immunity: {curse.name} blocked! (weapon immunity)")
            return False

    # Vaxxed: block Tier 2 curses
    if monster and monster.level == 2:
        if any(t.effect_id == "vaxxed" for t in player.traits):
            log.append(f"  Vaxxed!: {curse.name} blocked! (Tier 2 immunity)")
            return False

    # Immunized: negate next curse (one-shot, consumes trait)
    immunized_idx = next(
        (i for i, t in enumerate(player.traits) if t.effect_id == "immunized"), None
    )
    if immunized_idx is not None:
        consumed = player.traits.pop(immunized_idx)
        _fx.refresh_tokens(player)
        log.append(f"  Immunized: {curse.name} negated! (Immunized trait consumed)")
        return False

    # It's Wriggling: persistent — lose a trait whenever a new curse arrives
    if any(c.effect_id == "its_wriggling" for c in player.curses):
        if player.traits:
            lost = player.traits.pop()
            _fx.refresh_tokens(player)
            log.append(f"  It's Wriggling!: lost trait '{lost.name}' due to new curse.")

    # Apply the curse
    player.curses.append(curse)
    log.append(f"  Gained curse: {curse.name}")
    _fx.on_curse_gained(player, curse, log, decide_fn=decide_fn, other_players=other_players, select_fn=select_fn)
    return True


# ------------------------------------------------------------------
# Item draw hooks (Rake It In, Scavenger)
# ------------------------------------------------------------------

def _check_scavenger(
    player: Player,
    item: Item,
    item_deck: Deck[Item],
    log: list[str],
    decide_fn: Optional[Callable],
) -> Item:
    """Scavenger: may put drawn equip on bottom and draw another."""
    if not decide_fn:
        return item
    if any(t.effect_id == "scavenger" for t in player.traits):
        if decide_fn(f"Scavenger: Put {item.name} back and draw another?", log):
            item_deck.put_bottom(item)
            replacement = item_deck.draw()
            if replacement is not None:
                log.append(f"  Scavenger: {item.name} put back, drew {replacement.name}.")
                return replacement
            log.append("  Scavenger: deck empty after put-back.")
    return item


def _check_rake_it_in(
    player: Player,
    item_deck: Deck[Item],
    log: list[str],
    decide_fn: Optional[Callable],
) -> None:
    """Rake It In: may discard an equipped card to draw a second item."""
    if not decide_fn:
        return
    if not any(t.effect_id == "rake_it_in" for t in player.traits):
        return
    all_equips = player.helmets + player.chest_armor + player.leg_armor + player.weapons
    unlocked = [
        e for e in all_equips
        if not e.locked_by_curse_id
        or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
    ]
    if not unlocked:
        return
    if decide_fn("Rake It In!: Discard an equipped card to draw a second item?", log):
        discarded = unlocked[0]
        player.unequip(discarded)
        log.append(f"  Rake It In!: discarded {discarded.name}.")
        bonus_item = item_deck.draw()
        if bonus_item is not None:
            bonus_item = _check_scavenger(player, bonus_item, item_deck, log, decide_fn)
            log.append(f"  Rake It In!: drew bonus item {bonus_item.name}.")
            _offer_item(player, bonus_item, log, decide_fn)
        else:
            log.append("  Rake It In!: item deck empty — no bonus draw.")


# ------------------------------------------------------------------
# Pack / item offer helper
# ------------------------------------------------------------------

def _offer_item(
    player: Player,
    item: Item,
    log: list[str],
    decide_fn: Callable[[str, list[str]], bool],
) -> None:
    """Offer an item to the player: equip directly or add to pack.

    Handles all branching for full/empty slots and full/empty pack.
    When a pack item must be chosen to discard, index 0 is used (simulated choice).
    """
    # --- Consumable-item wrapper: add directly to player's consumables list ---
    if item.is_consumable:
        import copy as _copy
        from . import content as _C
        consumable = next((c for c in _C.CONSUMABLE_POOL if c.name == item.name), None)
        if consumable:
            if player.add_consumable_to_pack(_copy.copy(consumable)):
                log.append(f"  {item.name} added to consumables.")
            else:
                log.append(f"  {item.name} (consumable) — pack full, discarded.")
        else:
            log.append(f"  {item.name} (consumable) — unknown type, discarded.")
        return

    # --- Adaptable Blade: choose 1H (+4 Str) or 2H (+8 Str) before anything else ---
    if item.effect_id == "adaptable_blade":
        use_two_handed = decide_fn(
            "Adaptable Blade: Wield two-handed (+8 Str) instead of one-handed (+4 Str)?", log
        )
        if use_two_handed:
            item.hands = 2
            item.strength_bonus = 8
            log.append("  Adaptable Blade: configured as 2H weapon (+8 Str).")
        else:
            item.hands = 1
            item.strength_bonus = 4
            log.append("  Adaptable Blade: configured as 1H weapon (+4 Str).")

    want_equip = decide_fn(f"Equip {item.name} directly? (or add to pack)", log)

    if want_equip:
        if player.can_equip(item):
            player.equip(item)
            log.append(f"  {item.name} equipped.")
        else:
            # Slot full --- negotiate with currently equipped item
            slot_list = player._slot_list(item.slot)
            if not slot_list:
                # Can't equip and nothing to swap (e.g. weapon needs more hands than player has)
                if player.pack_slots_free > 0:
                    player.pack.append(item)
                    log.append(f"  Cannot equip {item.name} — added to pack.")
                else:
                    log.append(f"  Cannot equip {item.name} and pack is full — discarded.")
            else:
                current = slot_list[-1]
                keep_in_pack = decide_fn(
                    f"Slot full. Move {current.name} to pack to make room?", log
                )
                if keep_in_pack:
                    if player.pack_slots_free > 0:
                        player.unequip(current)
                        player.pack.append(current)
                        player.equip(item)
                        log.append(f"  {current.name} moved to pack. {item.name} equipped.")
                    else:
                        # Pack also full — discard first pack item to make room
                        evicted = player.pack.pop(0)
                        log.append(f"  Pack full \u2014 {evicted.name} discarded from pack.")
                        player.unequip(current)
                        player.pack.append(current)
                        player.equip(item)
                        log.append(f"  {current.name} moved to pack. {item.name} equipped.")
                else:
                    # Discard currently-equipped item, equip new
                    player.unequip(current)
                    player.equip(item)
                    log.append(f"  {current.name} discarded. {item.name} equipped.")
    else:
        # Add to pack
        if player.add_to_pack(item):
            log.append(f"  {item.name} added to pack.")
        else:
            # Pack full --- ask to cancel or discard a pack item
            cancel = decide_fn(f"Pack full! Cancel taking {item.name}?", log)
            if cancel:
                log.append(f"  Cancelled \u2014 {item.name} discarded.")
            else:
                evicted = player.pack.pop(0)
                player.pack.append(item)
                log.append(
                    f"  {evicted.name} discarded from pack. {item.name} added to pack."
                )


# ------------------------------------------------------------------
# Consumable phase helpers
# ------------------------------------------------------------------

_CONSUMABLE_PROXIMITY = 5  # max tile distance to allow bystander consumable play


def _apply_consumable_effect(
    consumable: Consumable,
    player: Player,
    active_player: Player,
    monster: Monster,
    log: list[str],
    decide_fn: Optional[Callable],
    select_fn: Optional[Callable],
    all_players: list[Player],
    monster_decks: Optional[dict],
    trait_deck,
    curse_deck,
) -> bool:
    """Apply one consumable's effect to the current encounter.

    Returns True if the monster was captured (encounter ends immediately).
    """
    eid = consumable.effect_id

    if eid == "monster_str_mod":
        delta = consumable.effect_value
        old = monster.strength
        monster.strength = max(0, monster.strength + delta)
        sign = "+" if delta >= 0 else ""
        log.append(
            f"  {player.name} used {consumable.name}: "
            f"monster strength {sign}{delta} ({old} \u2192 {monster.strength})."
        )

    elif eid in ("give_curse", "gain_trait"):
        tier = consumable.effect_tier
        deck = monster_decks.get(tier) if monster_decks else None
        drawn = deck.draw() if deck else None
        if drawn is None:
            log.append(f"  {consumable.name}: Tier-{tier} monster deck empty \u2014 no effect.")
            return False
        log.append(f"  {player.name} used {consumable.name}: drew {drawn.name}.")
        if eid == "give_curse":
            curse = (
                C.curse_for_monster(drawn) if drawn.curse_name
                else (curse_deck.draw() if curse_deck else None)
            )
            if curse is None:
                log.append(f"  {consumable.name}: no curse available.")
                return False
            targets = [p for p in all_players if p is not player]
            if targets and select_fn:
                idx = select_fn(
                    f"{consumable.name}: give '{curse.name}' to which player?",
                    [p.name for p in targets], log,
                )
                target = targets[max(0, min(idx, len(targets) - 1))]
            else:
                target = targets[0] if targets else active_player
            others_of_target = [p for p in all_players if p is not target]
            _apply_curse(target, curse, drawn, log,
                         decide_fn=decide_fn, other_players=others_of_target,
                         select_fn=select_fn)
        else:  # gain_trait
            trait = (
                C.trait_for_monster(drawn) if drawn.trait_name
                else (trait_deck.draw() if trait_deck else None)
            )
            if trait is None:
                log.append(f"  {consumable.name}: no trait available.")
                return False
            player.traits.append(trait)
            log.append(f"  {player.name} gained trait '{trait.name}'.")
            trait_items = _fx.on_trait_gained(player, trait, log)
            player.pending_trait_items.extend(trait_items)
            _fx.refresh_tokens(player)

    elif eid == "capture_monster":
        tier = consumable.effect_tier
        if monster.level != tier:
            log.append(
                f"  {consumable.name} requires a Tier-{tier} monster "
                f"(this is Tier-{monster.level}) \u2014 wasted."
            )
            return False
        if player.add_captured_monster(monster):
            log.append(
                f"  {player.name} captured {monster.name}! "
                f"Added to pack. No trait or curse."
            )
            return True  # encounter ends
        else:
            log.append(
                f"  {player.name}: pack full \u2014 {monster.name} not captured. Wasted."
            )

    return False


def _consumable_phase(
    active_player: Player,
    all_players: list[Player],
    monster: Monster,
    log: list[str],
    decide_fn: Callable,
    select_fn: Optional[Callable],
    monster_decks: Optional[dict],
    trait_deck,
    curse_deck,
) -> bool:
    """Offer consumables to nearby bystanders (one each), then to the active player (loop).

    Returns True if the monster was captured (caller should end the encounter).
    """
    # Phase 1: bystanders within proximity, in player-list order
    for p in all_players:
        if p is active_player:
            continue
        if abs(p.position - active_player.position) > _CONSUMABLE_PROXIMITY:
            continue
        usable = [c for c in p.consumables if c.effect_id]
        if not usable:
            continue
        if not decide_fn(
            f"{p.name} (tile {p.position}): play a consumable on "
            f"{monster.name} (tile {active_player.position})? (Y/N)",
            log,
        ):
            continue
        names = [c.name for c in usable]
        idx = select_fn(f"{p.name}: choose a consumable:", names, log) if select_fn else 0
        chosen = usable[max(0, min(idx, len(usable) - 1))]
        p.consumables.remove(chosen)
        if _apply_consumable_effect(
            chosen, p, active_player, monster, log,
            decide_fn, select_fn, all_players, monster_decks, trait_deck, curse_deck,
        ):
            return True

    # Phase 2: active player — may play multiple consumables
    while True:
        usable = [c for c in active_player.consumables if c.effect_id]
        if not usable:
            break
        if not decide_fn(
            f"{active_player.name}: play a consumable on {monster.name}? (Y/N)", log
        ):
            break
        names = [c.name for c in usable]
        idx = (
            select_fn(f"{active_player.name}: choose a consumable:", names, log)
            if select_fn else 0
        )
        chosen = usable[max(0, min(idx, len(usable) - 1))]
        active_player.consumables.remove(chosen)
        if _apply_consumable_effect(
            chosen, active_player, active_player, monster, log,
            decide_fn, select_fn, all_players, monster_decks, trait_deck, curse_deck,
        ):
            return True

    return False


# ------------------------------------------------------------------
# Individual encounter handlers
# ------------------------------------------------------------------

def encounter_chest(
    player: Player,
    item_deck: Deck[Item],
    log: list[str],
    decide_fn: Optional[Callable] = None,
) -> None:
    """RULES §7.1 --- draw an item, offer equip or pack choice."""
    item = item_deck.draw()
    if item is None:
        log.append("Chest: item deck is empty \u2014 nothing to draw.")
        return
    # Scavenger: may reject and draw another
    if decide_fn:
        item = _check_scavenger(player, item, item_deck, log, decide_fn)
    log.append(f"Chest: found {item.name} (+{item.strength_bonus} {item.slot.value})")
    if decide_fn is None:
        # Legacy / test path: auto-equip or discard
        if player.equip(item):
            log.append(f"  {item.name} equipped.")
        else:
            log.append(f"  No {item.slot.value} slot free — {item.name} discarded.")
    else:
        _offer_item(player, item, log, decide_fn)
        # Rake It In: may discard an equip to draw a second item
        _check_rake_it_in(player, item_deck, log, decide_fn)


def encounter_monster(
    player: Player,
    monster_deck: Deck[Monster],
    trait_deck: Deck[Trait],
    curse_deck: Deck[Curse],
    log: list[str],
    is_night: bool = False,
    flee: bool = False,
    decide_fn: Optional[Callable] = None,
    other_players: Optional[list] = None,
    all_players: Optional[list] = None,
    select_fn: Optional[Callable] = None,
    monster_decks: Optional[dict] = None,
    pre_drawn_monster: Optional[Monster] = None,
    extra_player_strength: int = 0,
) -> Optional[CombatResult]:
    """RULES §7.2 --- draw monster, resolve combat.

    If ``flee`` is True and the player's hero supports fleeing from
    monsters, the player escapes without penalty (no curse).
    The caller is responsible for moving the player back.

    ``all_players`` is the full list (for defeated-monster bonus checks).
    """
    monster = pre_drawn_monster if pre_drawn_monster is not None else monster_deck.draw()
    if monster is None:
        log.append("Monster: monster deck is empty \u2014 no encounter.")
        return None

    # --- Transmogrifier: may redraw monster once ---
    if monster is not None and decide_fn and player.has_equipped_item("transmogrifier"):
        if decide_fn(f"Transmogrifier: Send {monster.name} back and draw a new one?", log):
            original_name = monster.name
            monster_deck.put_bottom(monster)
            replacement = monster_deck.draw()
            if replacement is not None:
                log.append(f"  Transmogrifier: {original_name} sent to bottom, drew {replacement.name}.")
                monster = replacement
            else:
                log.append("  Transmogrifier: unexpected empty deck after put_bottom.")

    # --- Face Mask: auto-win vs Coronavirus ---
    if monster is not None and monster.name == "Coronavirus" and player.has_equipped_item("face_mask"):
        face_mask_item = next(
            (item for item in player.helmets if item.effect_id == "face_mask"), None
        )
        if face_mask_item is not None:
            face_mask_item.tokens += 5
            _fx.refresh_tokens(player)
            player.defeated_monsters.add(monster.name)
            trait = C.trait_for_monster(monster) if monster.trait_name else None
            if trait is None:
                trait = _pick_random_trait(trait_deck)
            if trait:
                player.traits.append(trait)
                log.append(
                    f"  Face Mask: auto-win vs Coronavirus! +5 Str tokens on Face Mask "
                    f"(total: +{face_mask_item.tokens}). Gained trait: {trait.name}"
                )
                trait_items = _fx.on_trait_gained(player, trait, log)
                player.pending_trait_items.extend(trait_items)
            else:
                log.append(
                    f"  Face Mask: auto-win vs Coronavirus! +5 Str tokens on Face Mask "
                    f"(total: +{face_mask_item.tokens})."
                )
            return CombatResult.WIN

    # --- I See Everything / I'll Come In Again: trait-based monster redraw ---
    if monster is not None and decide_fn:
        for trait_eid in ("i_see_everything", "ill_come_in_again"):
            redraw_trait = next(
                (t for t in player.traits if t.effect_id == trait_eid), None
            )
            if redraw_trait is not None:
                if decide_fn(f"{redraw_trait.name}: Send {monster.name} back and draw another?", log):
                    original_name = monster.name
                    monster_deck.put_bottom(monster)
                    replacement = monster_deck.draw()
                    if replacement is not None:
                        log.append(f"  {redraw_trait.name}: {original_name} sent to bottom, drew {replacement.name}.")
                        monster = replacement
                    break  # only one redraw per encounter

    # --- Flee check (Billfold: Fly, you dummy!) ---
    if flee and player.hero and player.hero.can_flee_monsters:
        log.append(
            f"Monster: {monster.name} (str {monster.strength}) appeared \u2014 "
            f"{player.name} flees! No curse received."
        )
        return None  # no combat result

    # --- Swiftness: may flee any combat (except Werbler) at no cost ---
    if decide_fn and any(t.effect_id == "swiftness" for t in player.traits):
        if decide_fn(f"Swiftness: Flee from {monster.name} at no cost?", log):
            log.append(f"  Swiftness: {player.name} flees from {monster.name}! No combat.")
            return None

    log.append(f"Monster: fighting {monster.name} (str {monster.strength})")

    # --- Pre-combat consumable phase ---
    if decide_fn:
        all_p: list[Player] = all_players if all_players is not None else [player]
        if _consumable_phase(
            active_player=player,
            all_players=all_p,
            monster=monster,
            log=log,
            decide_fn=decide_fn,
            select_fn=select_fn,
            monster_decks=monster_decks,
            trait_deck=trait_deck,
            curse_deck=curse_deck,
        ):
            log.append(f"  {monster.name} was captured \u2014 encounter ends.")
            return None

    # --- Rat Smasher: auto-win vs rats or cats ---
    _RAT_CAT_KEYWORDS = ("rat", "cat")
    rat_smasher_active = any(t.effect_id == "rat_smasher" for t in player.traits)
    monster_lower = monster.name.lower()
    if rat_smasher_active and any(kw in monster_lower for kw in _RAT_CAT_KEYWORDS):
        log.append(f"  Rat Smasher: auto-win against {monster.name}!")
        result = CombatResult.WIN
    # --- Creepy Hollywood Exec / Roofie Demon bonus auto-win ---
    elif monster.name == "Creepy Hollywood Exec" and _anyone_defeated(all_players, "Roofie Demon"):
        log.append("  Bonus: Roofie Demon has been defeated \u2014 auto-win!")
        result = CombatResult.WIN
    elif monster.name == "Roofie Demon" and _anyone_defeated(all_players, "Creepy Hollywood Exec"):
        log.append("  Bonus: Creepy Hollywood Exec has been defeated \u2014 auto-win!")
        result = CombatResult.WIN
    else:
        result = _resolve_with_pvp_penalties(player, monster, is_night, other_players, decide_fn, log, extra_player_strength=extra_player_strength)

    # --- Freeze Ray: may discard a movement card to skip trait/curse ---
    freeze_ray_used = False
    if decide_fn and player.has_equipped_item("freeze_ray") and player.movement_hand:
        if decide_fn(
            f"Freeze Ray: Discard a movement card to receive no trait or curse from {monster.name}?",
            log,
        ):
            discarded_card = player.movement_hand.pop(0)
            player.movement_discard.append(discarded_card)
            freeze_ray_used = True
            log.append(
                f"  Freeze Ray: discarded movement card {discarded_card} "
                f"\u2014 {monster.name} is frozen! No trait or curse."
            )

    if not freeze_ray_used:
        if result == CombatResult.WIN:
            player.defeated_monsters.add(monster.name)
            trait = C.trait_for_monster(monster) if monster.trait_name else None
            if trait is None:
                trait = _pick_random_trait(trait_deck)
            if trait:
                player.traits.append(trait)
                log.append(f"  Victory! Gained trait: {trait.name}")
                trait_items = _fx.on_trait_gained(player, trait, log)
                player.pending_trait_items.extend(trait_items)
            else:
                log.append("  Victory! (no traits left in deck)")
        elif result == CombatResult.LOSE:
            log.append("  Defeat!")
            # --- Leather Daddy: +1 Str token on loss ---
            for t in player.traits:
                if t.effect_id == "leather_daddy":
                    t.tokens += 1
                    log.append(f"  Leather Daddy: +1 Str token (total: +{t.tokens})")
            # --- It's Not Your Fault: may discard to take Trait instead of Curse ---
            not_your_fault = next(
                (t for t in player.traits if t.effect_id == "its_not_your_fault"), None
            )
            skip_curse = False
            if not_your_fault and decide_fn:
                if decide_fn("It's Not Your Fault!: Discard to gain monster's Trait instead?", log):
                    player.traits.remove(not_your_fault)
                    _fx.on_trait_lost(player, not_your_fault, log)
                    _fx.refresh_tokens(player)
                    trait = C.trait_for_monster(monster) if monster.trait_name else None
                    if trait is None:
                        trait = _pick_random_trait(trait_deck)
                    if trait:
                        player.traits.append(trait)
                        log.append(f"  It's Not Your Fault!: gained trait {trait.name} instead of curse!")
                        trait_items = _fx.on_trait_gained(player, trait, log)
                        player.pending_trait_items.extend(trait_items)
                    else:
                        log.append("  It's Not Your Fault!: no trait available.")
                    skip_curse = True
            if not skip_curse:
                curse = C.curse_for_monster(monster) if monster.curse_name else None
                if curse is None:
                    curse = _pick_random_curse(curse_deck)
                if curse:
                    _apply_curse(player, curse, monster, log,
                                 decide_fn=decide_fn, other_players=other_players,
                                 select_fn=select_fn)
                else:
                    log.append("  (no curses left in deck)")
            _apply_brunhilde_combat_loss(player, log)
        else:
            log.append("  Tie \u2014 no trait or curse gained.")
    return result


def _anyone_defeated(all_players: Optional[list], monster_name: str) -> bool:
    """Check if any player has defeated a specific monster."""
    if not all_players:
        return False
    return any(monster_name in p.defeated_monsters for p in all_players)


def _resolve_with_pvp_penalties(
    player: Player,
    monster: Monster,
    is_night: bool,
    other_players: Optional[list],
    decide_fn: Optional[Callable],
    log: list[str],
    extra_player_strength: int = 0,
) -> CombatResult:
    """Resolve combat, applying Strong Schlong PvP penalties first."""
    schlong_penalty = 0
    if other_players and decide_fn:
        for opp in other_players:
            schlong_trait = next(
                (t for t in opp.traits if t.effect_id == "strong_schlong" and t.tokens > 0),
                None,
            )
            if schlong_trait:
                if decide_fn(
                    f"Strong Schlong: {opp.name}, spend tokens to weaken {player.name}? "
                    f"({schlong_trait.tokens} tokens, each = -3 Str)",
                    log,
                ):
                    spent = schlong_trait.tokens
                    schlong_trait.tokens = 0
                    penalty = spent * 3
                    schlong_penalty += penalty
                    log.append(
                        f"  Strong Schlong: {opp.name} spent {spent} tokens \u2014 "
                        f"{player.name} gets -{penalty} Str this combat!"
                    )
    if schlong_penalty > 0:
        effective_monster = Monster(
            monster.name, strength=monster.strength + schlong_penalty, level=monster.level
        )
        return resolve_combat(player, effective_monster, is_night=is_night, extra_strength=extra_player_strength)
    return resolve_combat(player, monster, is_night=is_night, extra_strength=extra_player_strength)


def encounter_shop(
    player: Player,
    item_deck: Deck[Item],
    log: list[str],
    choose_index: int = 0,
    decide_fn: Optional[Callable] = None,
) -> None:
    """RULES §7.3 --- trade a trait for an item.

    ``choose_index`` selects which of the drawn items the player picks
    (default 0 = first).  In a real game this would be player input.
    The number of items drawn depends on the player's hero
    (Billfold draws 4 instead of 3).
    """
    if not player.traits:
        log.append("Shop: no traits to trade \u2014 shop cannot be used.")
        return

    draw_count = player.hero.shop_draw_count if player.hero else 3

    items = item_deck.draw_many(draw_count)
    if not items:
        log.append("Shop: item deck is empty \u2014 nothing to buy.")
        return

    idx = min(choose_index, len(items) - 1)
    chosen = items[idx]
    discarded_trait = player.traits.pop(0)  # discard oldest trait
    _fx.refresh_tokens(player)
    log.append(
        f"Shop: traded trait '{discarded_trait.name}' for {chosen.name}"
    )
    remaining_names = [it.name for it in items if it is not chosen]
    log.append(f"  Remaining items discarded: {remaining_names}")

    # Scavenger: may reject and draw another
    if decide_fn:
        chosen = _check_scavenger(player, chosen, item_deck, log, decide_fn)

    if decide_fn is None:
        # Legacy / test path: auto-equip or discard
        if player.equip(chosen):
            log.append(f"  {chosen.name} equipped.")
        else:
            log.append(f"  No {chosen.slot.value} slot free \u2014 {chosen.name} discarded.")
    else:
        _offer_item(player, chosen, log, decide_fn)
        # Rake It In: may discard an equip to draw a second item
        _check_rake_it_in(player, item_deck, log, decide_fn)


def encounter_blank(log: list[str]) -> None:
    """RULES §7.4 --- no effect."""
    log.append("Blank tile \u2014 nothing happens.")


def encounter_day_night(is_night: bool, log: list[str]) -> bool:
    """RULES §6 --- toggle day/night. Returns new is_night value."""
    new_state = not is_night
    if new_state:
        log.append("Day/Night tile \u2014 night falls! Fog of war descends.")
    else:
        log.append("Day/Night tile \u2014 dawn breaks! Fog lifts.")
    return new_state


# ------------------------------------------------------------------
# Boss combat modifiers
# ------------------------------------------------------------------

def _count_empty_equip_slots(player: Player) -> int:
    """Count unoccupied equipment slots (helmets + chest + legs + free weapon hands)."""
    empty = 0
    empty += max(0, player.helmet_slots - len(player.helmets))
    empty += max(0, player.chest_slots - len(player.chest_armor))
    empty += max(0, player.legs_slots - len(player.leg_armor))
    used_hands = sum(w.hands for w in player.weapons)
    empty += max(0, player.weapon_hands - used_hands)
    return empty


def _apply_miniboss_modifiers(
    player: Player,
    miniboss: Monster,
    log: list[str],
    is_night: bool = False,
) -> tuple[int, int, bool]:
    """Apply a mini-boss's ability (penalty) and weakness (bonus).

    Returns (player_str_mod, monster_str_mod, auto_win).
    """
    pid = miniboss.effect_id
    player_mod = 0
    monster_mod = 0
    auto_win = False

    # ── Tier 1 ─────────────────────────────────────────────────────

    if pid == "shielded_golem":
        # Ability (Armoured): each equipped card grants 1 less Str (min 0 per card)
        all_equipped = player.helmets + player.chest_armor + player.leg_armor + player.weapons
        penalty = sum(min(1, item.strength_bonus) for item in all_equipped)
        if penalty:
            player_mod -= penalty
            log.append(f"  Armoured: {penalty} equipped items each lose 1 Str.")
        # Weakness (Gotta Give 'Er): 2H weapons provide +5 additional Str
        two_h = sum(1 for w in player.weapons if w.hands >= 2)
        if two_h:
            bonus = two_h * 5
            player_mod += bonus
            log.append(f"  Gotta Give 'Er: {two_h} two-handed weapon(s) grant +{bonus} Str.")

    elif pid == "flaming_golem":
        # Ability (My Fajitas!): head+chest armour provide 2 less Str each (min 0)
        for item in player.helmets + player.chest_armor:
            reduction = min(2, item.strength_bonus)
            if reduction:
                player_mod -= reduction
        reduced = sum(min(2, i.strength_bonus) for i in player.helmets + player.chest_armor)
        if reduced:
            log.append(f"  My Fajitas!: head+chest armour lose {reduced} total Str.")
        # Weakness (Ross, Oven Mitts!): gauntlet → auto-win
        for item in player.helmets + player.chest_armor + player.leg_armor + player.weapons:
            if "gauntlet" in item.name.lower():
                auto_win = True
                log.append(f"  Ross, Oven Mitts!: {item.name} is a gauntlet — auto-win!")
                break

    elif pid == "ghostly_golem":
        # Ability (Run awaaaaaay!): handled post-combat (run back 10 on loss)
        # Weakness: if any equipped item has "Iron" in name → auto-win
        for item in player.helmets + player.chest_armor + player.leg_armor + player.weapons:
            if "iron" in item.name.lower():
                auto_win = True
                log.append(
                    f"  I Learned it from Supernatural: {item.name} contains iron — auto-win!"
                )
                break

    elif pid == "goaaaaaaaalem":
        # Ability (Make a Wall): if no free hand slots → −5 Str
        used_hands = sum(w.hands for w in player.weapons)
        if used_hands >= player.weapon_hands:
            player_mod -= 5
            log.append("  Make a Wall: no free hand slots — −5 Str.")
        # Weakness (No Jock): leg armour has ×2 Str (add the base leg str again)
        leg_bonus = sum(item.strength_bonus for item in player.leg_armor)
        if leg_bonus:
            player_mod += leg_bonus
            log.append(f"  No Jock: leg armour doubled — +{leg_bonus} Str.")

    # ── Tier 2 ─────────────────────────────────────────────────────

    elif pid == "sky_dragon":
        # Ability: all weapons except guns provide 0 Str
        non_gun_str = sum(w.strength_bonus for w in player.weapons if not w.is_gun)
        if non_gun_str:
            player_mod -= non_gun_str
            log.append(f"  You Will Not Get This: non-gun weapons lose {non_gun_str} Str.")
        # Weakness: guns provide +5 Str each
        gun_count = sum(1 for w in player.weapons if w.is_gun)
        if gun_count:
            bonus = gun_count * 5
            player_mod += bonus
            log.append(f"  You Got This: {gun_count} gun(s) grant +{bonus} Str.")

    elif pid == "crossroads_demon":
        # Ability (Hypnotic Gaze): if not wearing head armour → −10 Str
        if not player.helmets:
            player_mod -= 10
            log.append("  Hypnotic Gaze: no head armour — −10 Str.")
        # Weakness (A Fair Exchange): handled via pre-combat interactive prompt

    elif pid == "the_watcher":
        # Ability (I Consume All): cannot use consumables — handled by caller
        # (resolve_combat called with use_consumables=False)
        # Weakness (Call of the Void): empty equip slots provide +2 Str each
        empty = _count_empty_equip_slots(player)
        if empty:
            bonus = empty * 2
            player_mod += bonus
            log.append(f"  Call of the Void: {empty} empty slot(s) grant +{bonus} Str.")

    elif pid == "ogre_cutpurse":
        # Ability + Weakness: handled by pre-combat function _ogre_pre_combat
        pass

    return player_mod, monster_mod, auto_win


def _ogre_pre_combat(player: Player, miniboss: Monster, log: list[str]) -> int:
    """Ogre Cutpurse: discard all pack items; add equipped items' Str to monster.

    Also grants +5 player Str if pack was already empty.
    Returns monster_str_modifier.
    """
    monster_mod = 0
    pack_was_empty = (
        len(player.pack) == 0
        and len(player.captured_monsters) == 0
        and len(player.consumables) == 0
    )

    if pack_was_empty:
        log.append("  Empty-Handed: pack was already empty — +5 Str to player!")
        # This is a player bonus, but we encode it as negative monster mod
        monster_mod -= 5
    else:
        # Discard all pack contents
        equip_str_total = 0
        if player.pack:
            for item in player.pack:
                equip_str_total += item.strength_bonus
            names = [i.name for i in player.pack]
            log.append(f"  Ogre Cutpurse: discarded pack items: {', '.join(names)}")
            player.pack.clear()
        if player.captured_monsters:
            names = [m.name for m in player.captured_monsters]
            log.append(f"  Ogre Cutpurse: discarded captured monsters: {', '.join(names)}")
            player.captured_monsters.clear()
        if player.consumables:
            names = [c.name for c in player.consumables]
            log.append(f"  Ogre Cutpurse: discarded consumables: {', '.join(names)}")
            player.consumables.clear()
        if equip_str_total:
            monster_mod += equip_str_total
            log.append(
                f"  Ogre Cutpurse: discarded items add +{equip_str_total} "
                f"Str to the Ogre!"
            )

    return monster_mod


def _apply_werbler_modifiers(
    player: Player,
    werbler: Monster,
    log: list[str],
    is_night: bool = False,
) -> tuple[int, int]:
    """Apply a werbler's abilities (combat modifiers only).

    Returns (player_str_mod, monster_str_mod).
    Post-combat loss effects are handled separately.
    """
    wid = werbler.effect_id
    player_mod = 0
    monster_mod = 0

    if wid == "brady":
        # Big and Tall: melee weapons have −3 Str each
        melee_count = sum(1 for w in player.weapons if not w.is_ranged)
        if melee_count:
            penalty = melee_count * 3
            player_mod -= penalty
            log.append(f"  Big and Tall: {melee_count} melee weapon(s) lose {penalty} Str.")
        # Nice Hat: accumulated bonus from prior thefts (display only)
        nice_hat = getattr(werbler, "_brady_nice_hat_bonus", 0)
        if nice_hat:
            log.append(f"  Nice Hat: +{nice_hat} Str from stolen head armour")

    elif wid == "harry":
        # Light it up!: +10 Str during the day
        if not is_night:
            monster_mod += 10
            log.append("  Light it up!: daytime — werbler gains +10 Str.")

    elif wid == "ar_meg_geddon":
        # All-Mother: minions refuse to fight
        minion_str = _fx.total_minion_strength(player)
        if minion_str:
            player_mod -= minion_str
            log.append(
                f"  All-Mother: minions refuse to fight — −{minion_str} Str."
            )

    elif wid == "johnil":
        # Stretchy: 1H weapons have −4 Str each
        one_h = sum(1 for w in player.weapons if w.hands == 1)
        if one_h:
            penalty = one_h * 4
            player_mod -= penalty
            log.append(f"  Stretchy: {one_h} one-handed weapon(s) lose {penalty} Str.")

    return player_mod, monster_mod


def _apply_werbler_loss(
    player: Player,
    werbler: Monster,
    log: list[str],
    monster_deck_l3: Optional[Deck[Monster]] = None,
    curse_deck: Optional[Deck[Curse]] = None,
    select_fn: Optional[Callable] = None,
) -> None:
    """Apply a werbler's on-loss penalty."""
    wid = werbler.effect_id

    if wid == "brady":
        # Nice Hat: steal head armour (max 2 thefts tracked on monster)
        stolen_count = getattr(werbler, "_brady_thefts", 0)
        if stolen_count >= 2:
            log.append("  Nice Hat: Brady has already stolen 2 helmets — ability inactive.")
        elif not player.helmets:
            log.append("  Nice Hat: no head armour to steal (doesn't count towards limit).")
        else:
            helmet = player.helmets.pop(0)
            stolen_str = helmet.strength_bonus
            werbler.strength += stolen_str
            werbler._brady_thefts = stolen_count + 1  # type: ignore[attr-defined]
            werbler._brady_nice_hat_bonus = getattr(werbler, "_brady_nice_hat_bonus", 0) + stolen_str  # type: ignore[attr-defined]
            _fx.refresh_tokens(player)
            log.append(
                f"  Nice Hat: Brady stole {helmet.name} (+{stolen_str} Str)! "
                f"Brady now has {werbler.strength} Str "
                f"({werbler._brady_thefts}/2 thefts)."  # type: ignore[attr-defined]
            )

    elif wid == "harry":
        # Tainted: draw T3 monster card and take its curse
        if monster_deck_l3 and curse_deck:
            m = monster_deck_l3.draw()
            if m and m.curse_name:
                curse = C.curse_for_monster(m)
                if curse:
                    player.curses.append(curse)
                    _fx.refresh_tokens(player)
                    log.append(
                        f"  Tainted: drew {m.name} — gained curse: {curse.name}."
                    )
                else:
                    log.append(f"  Tainted: drew {m.name} but curse not in registry.")
            elif m:
                log.append(f"  Tainted: drew {m.name} but it has no curse.")
            else:
                log.append("  Tainted: no L3 monsters left in deck.")

    elif wid == "ar_meg_geddon":
        # Schmegged: discard chest and leg equipment
        discarded = []
        for item in list(player.chest_armor):
            player.chest_armor.remove(item)
            discarded.append(item.name)
        for item in list(player.leg_armor):
            player.leg_armor.remove(item)
            discarded.append(item.name)
        if discarded:
            _fx.refresh_tokens(player)
            log.append(f"  Schmegged: discarded {', '.join(discarded)}.")
        else:
            log.append("  Schmegged: no chest or leg equipment to discard.")

    elif wid == "johnil":
        # Slurp!: lose 2 traits of player's choice
        if not player.traits:
            log.append("  Slurp!: no traits to lose.")
        elif len(player.traits) <= 2:
            names = [t.name for t in player.traits]
            player.traits.clear()
            _fx.refresh_tokens(player)
            log.append(f"  Slurp!: lost all traits: {', '.join(names)}.")
        else:
            # Interactive selection (via select_fn)
            if select_fn:
                chosen: list = select_fn(
                    player.traits,
                    min(2, len(player.traits)),
                    "Choose 2 traits to lose (Slurp!):",
                )
            else:
                # Fallback: lose the first 2 traits
                chosen = player.traits[:2]
            removed_names = []
            for t in list(chosen):
                if t in player.traits:
                    player.traits.remove(t)
                    _fx.on_trait_lost(player, t, log)
                    removed_names.append(t.name)
            _fx.refresh_tokens(player)
            log.append(f"  Slurp!: lost traits: {', '.join(removed_names)}.")


def encounter_miniboss(
    player: Player,
    miniboss: Monster,
    item_deck: Deck[Item],
    log: list[str],
    is_night: bool = False,
    flee: bool = False,
    decide_fn: Optional[Callable] = None,
    other_players: Optional[list] = None,
    select_fn: Optional[Callable] = None,
    crossroads_discards: Optional[list[Item]] = None,
    pre_run_ogre: Optional[tuple[int, int]] = None,
) -> Optional[CombatResult]:
    """Fight a miniboss. Must win to progress.

    ``pre_run_ogre`` (monster_mod, player_mod): when provided, skip calling
    ``_ogre_pre_combat`` — it was already run at fight-start to update display.

    Parameters
    ----------
    item_deck :
        The item deck for the NEXT tier (T2 for MB1, T3 for MB2).
        On victory the player draws 1 item from this deck.
    crossroads_discards :
        Items the player chose to discard for Crossroads Demon's
        "Fair Exchange" weakness.  On win, draw that many T3 items.
        Caller handles the interactive discard prompt before calling.
    """
    # --- Flee check (Billfold: Fly, you dummy!) ---
    if flee and player.hero and player.hero.can_flee_miniboss:
        log.append(
            f"Miniboss: {miniboss.name} (str {miniboss.strength}) \u2014 "
            f"{player.name} flees! No curse received."
        )
        return None  # no combat, caller handles backward move

    log.append(f"Miniboss: fighting {miniboss.name} (str {miniboss.strength})")

    # --- Pre-combat: Ogre Cutpurse pack pillage ---
    if pre_run_ogre is not None:
        # Already run at fight-start (pre-fight display); use stored values.
        ogre_monster_mod, ogre_player_mod_enc = pre_run_ogre
    else:
        ogre_monster_mod, ogre_player_mod_enc = 0, 0
        if miniboss.effect_id == "ogre_cutpurse":
            ogre_monster_mod, ogre_player_mod_enc = _ogre_pre_combat(player, miniboss, log)

    # --- Boss combat modifiers ---
    player_mod, monster_mod, auto_win = _apply_miniboss_modifiers(
        player, miniboss, log, is_night=is_night,
    )
    monster_mod += ogre_monster_mod
    player_mod += ogre_player_mod_enc

    if auto_win:
        result = CombatResult.WIN
        log.append("  AUTO-WIN triggered!")
    else:
        # Build effective monster with modified strength
        effective_strength = miniboss.strength + monster_mod
        # Player modifier applied via a temporary one-shot approach:
        # We adjust monster strength in the opposite direction to avoid
        # touching the player's real combat_strength calculation.
        effective_strength -= player_mod
        effective_strength = max(0, effective_strength)
        effective_monster = Monster(
            miniboss.name, strength=effective_strength, level=miniboss.level,
        )
        result = resolve_combat(player, effective_monster, is_night=is_night)

    if result == CombatResult.WIN:
        player.defeated_monsters.add(miniboss.name)
        log.append(f"  Victory over {miniboss.name}!")

        # --- Win reward: draw 1 item from next-tier deck ---
        reward = item_deck.draw()
        if reward:
            log.append(f"  Win reward: drew {reward.name} from next-tier deck.")
        else:
            log.append("  Win reward: item deck is empty — no reward.")

        # --- Crossroads Demon: Fair Exchange bonus draws ---
        if crossroads_discards and miniboss.effect_id == "crossroads_demon":
            extra_count = len(crossroads_discards)
            drawn_items: list[Item] = []
            for _ in range(extra_count):
                extra = item_deck.draw()
                if extra:
                    drawn_items.append(extra)
            if drawn_items:
                names = [i.name for i in drawn_items]
                log.append(
                    f"  Fair Exchange: drew {len(drawn_items)} T3 item(s): "
                    f"{', '.join(names)}."
                )
            else:
                log.append("  Fair Exchange: deck empty — no bonus items.")
            # Return rewards including the bonus draws; caller handles placement
            return result  # caller gets reward + drawn_items via the deck

        return result  # caller handles the reward item placement

    elif result == CombatResult.LOSE:
        # --- Leather Daddy: +1 Str token on loss ---
        for t in player.traits:
            if t.effect_id == "leather_daddy":
                t.tokens += 1
                log.append(f"  Leather Daddy: +1 Str token (total: +{t.tokens})")
        log.append("  Defeat! You remain on the miniboss tile.")
        # --- Ghostly Golem: run back 10 spaces ---
        if miniboss.effect_id == "ghostly_golem":
            new_pos = max(1, player.position - 10)
            log.append(
                f"  Run awaaaaaay!: sent back 10 spaces to tile {new_pos}."
            )
            player.position = new_pos
        # --- Brunhilde: Skimpy Armour ---
        _apply_brunhilde_combat_loss(player, log)
    else:
        log.append("  Tie \u2014 no progress, remain on tile.")
    return result


def encounter_werbler(
    player: Player,
    werbler: Monster,
    curse_deck: Deck[Curse],
    log: list[str],
    is_night: bool = False,
    decide_fn: Optional[Callable] = None,
    other_players: Optional[list] = None,
    select_fn: Optional[Callable] = None,
    monster_deck_l3: Optional[Deck[Monster]] = None,
) -> tuple[Optional[CombatResult], GameStatus]:
    """Final boss fight. Win → game won; lose → back to tile 61."""
    log.append(f"THE WERBLER: fighting {werbler.name} (str {werbler.strength})")

    # KNEEL! curse: +10 Werbler strength per curse stack
    kneel_count = sum(1 for c in player.curses if c.effect_id == "kneel")
    kneel_bonus = 0
    if kneel_count:
        kneel_bonus = 10 * kneel_count
        log.append(
            f"  KNEEL!: Werbler strength +{kneel_bonus} "
            f"due to {kneel_count} curse(s)!"
        )

    # --- Werbler-specific combat modifiers ---
    player_mod, monster_mod = _apply_werbler_modifiers(
        player, werbler, log, is_night=is_night,
    )
    monster_mod += kneel_bonus

    # Build effective monster
    effective_strength = werbler.strength + monster_mod - player_mod
    effective_strength = max(0, effective_strength)
    effective_werbler = Monster(
        werbler.name, strength=effective_strength, level=werbler.level,
    )
    result = resolve_combat(player, effective_werbler, is_night=is_night)

    if result == CombatResult.WIN:
        log.append("  VICTORY! You defeated your Werbler!")
        return result, GameStatus.WON

    elif result == CombatResult.LOSE:
        # --- Leather Daddy: +1 Str token on loss ---
        for t in player.traits:
            if t.effect_id == "leather_daddy":
                t.tokens += 1
                log.append(f"  Leather Daddy: +1 Str token (total: +{t.tokens})")
        # --- KNEEL!: self-removes on Werbler loss ---
        kneel_curses = [c for c in player.curses if c.effect_id == "kneel"]
        if kneel_curses:
            for kc in kneel_curses:
                player.curses.remove(kc)
            log.append(
                f"  KNEEL!: {len(kneel_curses)} curse(s) discarded after Werbler loss."
            )
        # --- Werbler-specific loss effects ---
        _apply_werbler_loss(
            player, werbler, log,
            monster_deck_l3=monster_deck_l3,
            curse_deck=curse_deck,
            select_fn=select_fn,
        )
        # --- Brunhilde: Skimpy Armour ---
        _apply_brunhilde_combat_loss(player, log)
        # Send back to tile 61
        player.position = 61
        log.append("  Defeat! Sent back to tile 61 (start of Level 3).")
        return result, GameStatus.IN_PROGRESS
    else:
        log.append("  Tie \u2014 no progress. Remain on tile 90.")
        return result, GameStatus.IN_PROGRESS

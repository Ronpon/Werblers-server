"""Flask web server for Werblers board game."""
from __future__ import annotations
import os
import sys
from typing import Optional
# Allow importing werblers_engine from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, jsonify, render_template, request, send_from_directory
from werblers_engine.game import Game
from werblers_engine.heroes import HEROES, HeroId
from werblers_engine.types import TileType
from werblers_engine import content as C
from werblers_engine import effects as _fx
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "Images")
MUSIC_DIR  = os.path.join(BASE_DIR, "Music")
VIDEOS_DIR = os.path.join(BASE_DIR, "Videos")
_game: Optional[Game] = None
_last_log: list[str] = []
_pending_log: list[str] = []   # log lines from begin_move, prepended to resolve_offer log
_TOKEN_MAP: dict[str, str] = {
    "BILLFOLD":  "Assorted UI Images/Billfold Token.png",
    "GREGORY":   "Assorted UI Images/Gregory Token.png",
    "BRUNHILDE": "Assorted UI Images/Brunhilde Token.png",
    "RIZZT":     "Assorted UI Images/Rizzt Token.png",
}
_CARD_IMG_MAP: dict[str, str] = {
    "BILLFOLD":  "Heroes/Billfold Baggains Card.png",
    "GREGORY":   "Heroes/Gregory Card.png",
    "BRUNHILDE": "Heroes/Brunhilde the Bodacious Card.png",
    "RIZZT":     "Heroes/Rizzt No'Cappin Card.png",
}

_HERO_ANIM_MAP: dict[str, dict[str, str]] = {
    "BILLFOLD": {
        "general": "Hero Animations/Billfold General.mp4",
        "victory": "Hero Animations/Billfold Victory.mp4",
        "defeat":  "Hero Animations/Billfold Defeat.mp4",
    },
    "GREGORY": {
        "general": "Hero Animations/Gregory General.mp4",
        "victory": "Hero Animations/Gregory Victory.mp4",
        "defeat":  "Hero Animations/Gregory Defeat.mp4",
    },
    "BRUNHILDE": {
        "general": "Hero Animations/Brumhilde General.mp4",
        "victory": "Hero Animations/Brumhilde Victory.mp4",
        "defeat":  "Hero Animations/Brumhilde Defeat.mp4",
    },
    "RIZZT": {
        "general": "Hero Animations/Rizzt General.mp4",
        "victory": "Hero Animations/Rizzt Victory.mp4",
        "defeat":  "Hero Animations/Rizzt Defeat.mp4",
    },
}
# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")
@app.route("/images/<path:filename>")
def serve_image(filename: str):
    return send_from_directory(IMAGES_DIR, filename)
@app.route("/music/<path:filename>")
def serve_music(filename: str):
    return send_from_directory(MUSIC_DIR, filename)
@app.route("/videos/<path:filename>")
def serve_video(filename: str):
    return send_from_directory(VIDEOS_DIR, filename)
@app.route("/api/heroes")
def api_heroes():
    result = []
    for hero_id, hero in HEROES.items():
        result.append({
            "id":          hero_id.name,
            "name":        hero.name,
            "title":       hero.title,
            "description": hero.description,
            "card_image":  _CARD_IMG_MAP.get(hero_id.name, ""),
            "animations":  _HERO_ANIM_MAP.get(hero_id.name, {}),
        })
    return jsonify(result)
@app.route("/api/new_game", methods=["POST"])
def api_new_game():
    global _game, _last_log, _pending_log
    data: dict = request.get_json(force=True) or {}
    hero_id_strs: list[str] = data.get("hero_ids", [])
    num_players: int = len(hero_id_strs) if hero_id_strs else data.get("num_players", 1)
    seed: Optional[int] = data.get("seed", None)
    hero_ids = [HeroId[h] for h in hero_id_strs] if hero_id_strs else None
    _game = Game(num_players=num_players, hero_ids=hero_ids, seed=seed)
    for p in _game.players:
        _game.draw_movement_cards(p)
    _pending_log = []
    _last_log = ["New game started!"]
    return jsonify({"ok": True, "state": _build_state()})
@app.route("/api/state")
def api_state():
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    return jsonify(_build_state())
# ------------------------------------------------------------------
# Interactive turn API
# ------------------------------------------------------------------
@app.route("/api/get_abilities")
def api_get_abilities():
    """Return available 'you may' abilities for the current player."""
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    abilities = _game.get_available_abilities()
    return jsonify({"abilities": abilities})
@app.route("/api/begin_move", methods=["POST"])
def api_begin_move():
    """Phase 1: play a movement card, reveal tile, pause if chest/shop."""
    global _last_log, _pending_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    # Guard: reject if there's already an unresolved pending state
    if _game._pending_offer is not None:
        return jsonify({"error": "Resolve the current offer first"}), 409
    if _game._pending_combat is not None:
        return jsonify({"error": "Resolve the current combat first"}), 409
    data: dict = request.get_json(force=True) or {}
    card_index: int = int(data.get("card_index", 0))
    flee: bool = bool(data.get("flee", False))
    activated: dict = data.get("activated", {})
    direction: str = data.get("direction", "forward")
    result = _game.begin_move(card_index=card_index, flee=flee, activated=activated, direction=direction)
    log = result.get("log", [])
    moved_to = result.get("moved_to")
    tile_type = result.get("tile_type", "")
    bg_map = {1: "Backgrounds/Forest Background.png", 2: "Backgrounds/Cave Background.png", 3: "Backgrounds/Dungeon Background.png"}
    background = bg_map.get(_tile_level(moved_to) if moved_to else 1, bg_map[1])
    tile_scene = {"tile_type": tile_type, "background": background, "moved_to": moved_to}
    if result["phase"] in ("done", "combat"):
        _pending_log = []
        _last_log = log
        combat_info = result.get("combat_info")
        if combat_info:
            combat_info = _enrich_combat_info(combat_info)
        return jsonify({"phase": result["phase"], "state": _build_state(), "combat_info": combat_info, "tile_scene": tile_scene})
    elif result["phase"] == "charlie_work":
        _pending_log = log
        _last_log = log
        return jsonify({
            "phase":      "charlie_work",
            "level":      result.get("level", 1),
            "state":      _build_state(),
            "tile_scene": tile_scene,
            "log":        log,
        })
    elif result["phase"] == "mystery":
        _pending_log = log
        _last_log = log
        me = result.get("mystery_event", {})
        img_name = me.get('image_name') or me['name']
        me["image"] = f"Events/{img_name} Tier {me['tier']}.png"
        return jsonify({
            "phase":         "mystery",
            "mystery_event": me,
            "state":         _build_state(),
            "tile_scene":    tile_scene,
        })
    else:
        _pending_log = log
        _last_log = log
        raw_offer = result["offer"]
        enriched_items = [
            {**item, "card_image": _item_card_image_from_dict(item)}
            for item in raw_offer.get("items", [])
        ]
        offer = {**raw_offer, "items": enriched_items}
        return jsonify({
            "phase":      result["phase"],
            "offer":      offer,
            "state":      _build_state(),
            "tile_scene": tile_scene,
        })
@app.route("/api/resolve_charlie_work", methods=["POST"])
def api_resolve_charlie_work():
    """Resolve the No More Charlie Work decision (phase == 'charlie_work')."""
    global _last_log, _pending_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    use_it: bool = bool(data.get("use_it", False))
    result = _game.resolve_charlie_work(use_it=use_it)
    log = _pending_log + result.get("log", [])
    _pending_log = []
    _last_log = log
    combat_info = result.get("combat_info")
    if combat_info:
        combat_info = _enrich_combat_info(combat_info)
    return jsonify({"phase": result["phase"], "state": _build_state(), "combat_info": combat_info})

@app.route("/api/use_ill_come_in_again", methods=["POST"])
def api_use_ill_come_in_again():
    """Use I'll Come In Again / I See Everything: return current monster and draw a new one."""
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    result = _game.use_ill_come_in_again()
    if "error" in result:
        return jsonify(result), 400
    combat_info = _enrich_combat_info(result["combat_info"])
    return jsonify({"phase": "combat", "state": _build_state(), "combat_info": combat_info})

@app.route("/api/resolve_offer", methods=["POST"])
def api_resolve_offer():
    """Phase 2: apply player item choices, complete the turn."""
    global _last_log, _pending_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    choices: dict = request.get_json(force=True) or {}
    result = _game.resolve_offer(choices=choices)
    combined_log = _pending_log + result.get("log", [])
    _pending_log = combined_log
    _last_log = combined_log
    if result.get("phase") == "rake_it_in":
        # Rake It In pauses before the turn ends — enrich equips/shop items with card images
        equips = [
            {**e, "card_image": _item_card_image_from_dict(e)}
            for e in result.get("equips", [])
        ]
        pack_items = [
            {**i, "card_image": _item_card_image_from_dict(i)}
            for i in result.get("pack_items", [])
        ]
        consumable_items = [
            {**i, "card_image": _consumable_card_image(i.get("name", ""))}
            for i in result.get("consumable_items", [])
        ]
        shop_remaining = [
            {**i, "card_image": _item_card_image_from_dict(i)}
            for i in result.get("shop_remaining", [])
        ]
        return jsonify({
            "phase": "rake_it_in",
            "sub_type": result.get("sub_type", "chest"),
            "equips": equips,
            "pack_items": pack_items,
            "consumable_items": consumable_items,
            "shop_remaining": shop_remaining,
            "state": _build_state(),
            "log": combined_log,
        })
    _pending_log = []
    return jsonify({"phase": "done", "state": _build_state()})


# ------------------------------------------------------------------
# Mystery event resolution
# ------------------------------------------------------------------
@app.route("/api/resolve_mystery", methods=["POST"])
def api_resolve_mystery():
    """Resolve a pending mystery event.

    JSON body:
        action: str —  "open" | "spin" | "smith" | "accept" | "give" | "skip"
        wager_index:   int  (pack slot for mystery_box / fairy_king give)
        smith_indices:  list[int]  (3 pack slot indices for the smith trade)
        smith_equip_index: int  (equipped item index for tier-3 smith enhancement)
    """
    import traceback as _tb
    global _last_log, _pending_log
    try:
        return _api_resolve_mystery_inner()
    except Exception as exc:
        tb = _tb.format_exc()
        _tb.print_exc()
        return jsonify({"error": f"Server error in resolve_mystery: {exc}\n\nTraceback:\n{tb}"}), 500

def _api_resolve_mystery_inner():
    global _last_log, _pending_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    po = _game._pending_offer
    if po is None or po.get("type") != "mystery":
        return jsonify({"error": "No pending mystery event"}), 400

    data: dict = request.get_json(force=True) or {}
    event = po["event"]
    player = _game.current_player
    level = po["level"]
    log: list[str] = po.get("log", _pending_log or [])

    from werblers_engine import mystery as _mys

    result: dict = {}
    event_id = event.event_id
    tier = event.tier

    # Handle skip/decline — finish the turn without resolving the event
    action = data.get("action", "")
    if action == "skip":
        log.append(f"Declined the {event.name} event.")
        _game._pending_offer = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _pending_log = []
        _last_log = log
        return jsonify({
            "phase": "done",
            "prize_type": "skip",
            "mystery_result": "Declined",
            "state": _build_state(),
        })

    if event_id == "mystery_box":
        wager_idx = int(data.get("wager_index", -1))
        result = _mys.resolve_mystery_box(
            player, tier, wager_idx,
            _game.item_decks, _game.monster_decks, _game.trait_deck,
            log,
        )

    elif event_id == "the_wheel":
        result = _mys.resolve_the_wheel(
            player, tier,
            _game.item_decks, _game.monster_decks, _game.trait_deck,
            log,
        )

    elif event_id == "the_smith":
        smith_indices = data.get("smith_indices", [])
        smith_equip_idx = int(data.get("smith_equip_index", -1))
        result = _mys.resolve_the_smith(
            player, tier, _game.item_decks,
            smith_indices, smith_equip_idx, log,
        )

    elif event_id == "bandits":
        result = _mys.resolve_bandits(player, log)

    elif event_id == "thief":
        result = _mys.resolve_thief(player, log)

    elif event_id == "beggar":
        give_idx = int(data.get("wager_index", -1))
        result = _mys.resolve_beggar(
            player, tier, _game.item_decks, give_idx, log,
        )

    else:
        log.append(f"Unknown mystery event: {event_id}")
        result = {"prize_type": "nothing", "label": "Unknown event"}

    # If the prize is an item, set up a pending offer for placement
    if result.get("prize_type") == "item" and result.get("item"):
        item = result["item"]
        _game._pending_offer = {
            "type": "chest",
            "level": level,
            "items": [item],
            "moved_from": po["moved_from"], "moved_to": po["moved_to"],
            "card_played": po["card_played"], "tile_type": po["tile_type"],
        }
        _last_log = log
        _pending_log = log
        return jsonify({
            "phase": "offer_chest",
            "event_id": event_id,
            "prize_type": result.get("prize_type", ""),
            "mystery_result": result.get("label", ""),
            "state": _build_state(),
            "offer": {"items": [_item_to_dict_from_obj(item)]},
        })

    # Fairy King reveal: keep pending offer alive so player can choose a T3 reward
    if result.get("prize_type") == "fairy_king_reveal":
        reward_items = result.get("reward_items", [])
        _game._pending_offer = {
            "type": "fairy_king_reward",
            "reward_items": reward_items,
            "moved_from": po["moved_from"], "moved_to": po["moved_to"],
            "card_played": po["card_played"], "tile_type": po["tile_type"],
            "log": log,
        }
        _last_log = log
        _pending_log = log
        return jsonify({
            "phase": "fairy_king_reveal",
            "mystery_result": result.get("label", ""),
            "state": _build_state(),
            "reward_items": [_item_to_dict_from_obj(i) for i in reward_items],
        })

    # Beggar accepted a gift (not the 3rd) — finish turn but signal UI
    if result.get("prize_type") == "beggar_thank":
        _game._pending_offer = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _pending_log = []
        _last_log = log
        return jsonify({
            "phase": "beggar_thank",
            "event_id": event_id,
            "prize_type": "beggar_thank",
            "mystery_result": result.get("label", ""),
            "state": _build_state(),
        })

    # Error results — Don't finish the turn; let the player retry
    if result.get("prize_type") == "error":
        _last_log = log
        return jsonify({"error": "Invalid selection — please try again.", "state": _build_state()}), 400

    # Otherwise (nothing, skip, trait, smith_enhance, gift_accepted, stolen)
    # — finish the turn
    _game._pending_offer = None
    _game._finish_post_encounter(player, log)
    _game._advance_turn()
    _pending_log = []
    _last_log = log

    # Build rich outcome payload so the frontend can display a proper outcome screen
    outcome: dict = {
        "phase": "done",
        "mystery_result": result.get("label", ""),
        "prize_type": result.get("prize_type", "nothing"),
        "event_id": event_id,
        "state": _build_state(),
    }
    # Include item/trait/stolen info depending on prize_type
    if result.get("item_name"):
        outcome["item_name"] = result["item_name"]
    if result.get("item"):
        outcome["card_image"] = _item_card_image(result["item"])
    if result.get("items"):
        outcome["stolen_items"] = result["items"]
    if result.get("trait") and hasattr(result["trait"], "name"):
        outcome["trait_name"] = result["trait"].name
        outcome["trait_description"] = C.TRAIT_DESCRIPTIONS.get(result["trait"].name, "")
    if result.get("curse_name"):
        outcome["curse_name"] = result["curse_name"]
        outcome["curse_description"] = C.CURSE_DESCRIPTIONS.get(result["curse_name"], "")
    if result.get("monster_name") and result.get("prize_type") == "curse":
        outcome["monster_name"] = result["monster_name"]
        outcome["card_image"] = _monster_card_image(result["monster_name"])
    return jsonify(outcome)


def _item_to_dict_from_obj(item) -> dict:
    """Serialize a types.Item object to dict for JSON (matching _item_to_dict pattern)."""
    return {
        "name": item.name,
        "slot": item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id": item.effect_id,
        "hands": item.hands,
        "is_consumable": item.is_consumable,
        "card_image": _item_card_image(item),
    }


@app.route("/api/resolve_fairy_king_reward", methods=["POST"])
def api_resolve_fairy_king_reward():
    """Player chooses one of the 3 T3 items offered by the Fairy King."""
    global _last_log, _pending_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    po = _game._pending_offer
    if po is None or po.get("type") != "fairy_king_reward":
        return jsonify({"error": "No pending Fairy King reward"}), 400

    data: dict = request.get_json(force=True) or {}
    choice = int(data.get("choice_index", -1))
    reward_items = po["reward_items"]
    if choice < 0 or choice >= len(reward_items):
        return jsonify({"error": "Invalid choice"}), 400

    player = _game.current_player
    chosen = reward_items[choice]
    log: list[str] = po.get("log", _pending_log or [])

    # Set up item placement like a chest offer
    _game._pending_offer = {
        "type": "chest",
        "level": 3,
        "items": [chosen],
        "moved_from": po["moved_from"], "moved_to": po["moved_to"],
        "card_played": po["card_played"], "tile_type": po["tile_type"],
    }
    log.append(f"The Fairy King bestows: {chosen.name}!")
    _last_log = log
    _pending_log = log
    return jsonify({
        "phase": "offer_chest",
        "mystery_result": f"Fairy King reward: {chosen.name}",
        "state": _build_state(),
        "offer": {"items": [_item_to_dict_from_obj(chosen)]},
    })


@app.route("/api/resolve_rake_it_in", methods=["POST"])
def api_resolve_rake_it_in():
    """Resolve the Rake It In decision (phase == 'rake_it_in').

    JSON body:
        use_it          : bool
        discard_slot    : "equip_helmet"|"equip_chest"|"equip_leg"|"equip_weapon"
        discard_idx     : int
        second_item_choice : int (shop only — which remaining item to take)
        placement       : "equip"|"pack"  (for bonus item)
    """
    global _last_log, _pending_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    use_it = bool(data.get("use_it", False))
    discard_slot = str(data.get("discard_slot", ""))
    discard_idx  = int(data.get("discard_idx", 0))
    second_item_choice = int(data.get("second_item_choice", -1))
    placement_choices = {k: data[k] for k in ("placement", "equip_action", "equip_item_index") if k in data}
    result = _game.resolve_rake_it_in(
        use_it=use_it,
        discard_slot=discard_slot,
        discard_idx=discard_idx,
        second_item_choice=second_item_choice,
        placement_choices=placement_choices,
    )
    combined_log = _pending_log + result.get("log", [])
    _pending_log = []
    _last_log = combined_log
    bonus = result.get("bonus_item")
    if bonus:
        bonus["card_image"] = _item_card_image_from_dict(bonus)
    return jsonify({"phase": "done", "state": _build_state(), "bonus_item": bonus})

@app.route("/api/equip_from_pack", methods=["POST"])
def api_equip_from_pack():
    """Move an item from pack to an equipment slot.

    Optional flags:
      ``force``   -- discard the displaced item when no free slot available.
      ``to_pack`` -- move the displaced item to the pack instead of discarding.
      ``displaced_actions`` -- list of dicts with {action: 'discard'|'to_pack', discard_pack_index: int} for each displaced item.
    """
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    pack_index = int(data.get("pack_index", 0))
    force   = bool(data.get("force",   False))
    to_pack = bool(data.get("to_pack", False))
    discard_pack_index = int(data.get("discard_pack_index", -1))
    equip_displaced = bool(data.get("equip_displaced", False))
    displaced_actions = data.get("displaced_actions", None)
    player = _game.current_player
    if pack_index < 0 or pack_index >= len(player.pack):
        return jsonify({"error": "Invalid pack index"}), 400
    item = player.pack[pack_index]
    if not player.can_equip(item):
        # --- Weapon slot: compute how many weapons must be displaced ---
        if item.slot.value == "weapon":
            hands_used = sum(w.hands for w in player.weapons)
            hands_free = player.weapon_hands - hands_used
            hands_to_free = item.hands - hands_free

            items_to_displace = []
            freed = 0
            for w in list(player.weapons):
                if freed >= hands_to_free:
                    break
                items_to_displace.append(w)
                freed += w.hands

            if len(items_to_displace) > 1:
                # Multi-displace: fire on ANY call (initial or force/to_pack) unless
                # displaced_actions already provided.
                if displaced_actions is None:
                    displaced_data = [{
                        "name": w.name,
                        "card_image": _item_card_image(w),
                        "hands": w.hands,
                        "strength_bonus": w.strength_bonus,
                    } for w in items_to_displace]
                    # After the new item leaves pack there will be +1 free slot for displaced weapons
                    return jsonify({
                        "error": "multi_displace",
                        "displaced_items": displaced_data,
                        "pack_slots_free": player.pack_slots_free + 1,
                    })
                else:
                    # Process each displaced item according to frontend instructions
                    # First, remove the new item from pack
                    try:
                        pi = player.pack.index(item)
                    except ValueError:
                        pi = pack_index
                    player.pack.pop(pi)

                    for i, w in enumerate(items_to_displace):
                        da = displaced_actions[i] if i < len(displaced_actions) else {"action": "discard"}
                        if da.get("action") == "to_pack":
                            dpi = int(da.get("discard_pack_index", -1))
                            if player.pack_slots_free <= 0:
                                if dpi >= 0:
                                    player.evict_pack_slot(dpi)
                                else:
                                    # No room and no pack slot to evict — discard instead
                                    player.unequip(w)
                                    continue
                            player.unequip(w)
                            player.pack.append(w)
                        else:  # discard
                            player.unequip(w)
                    player.equip(item)
                    from werblers_engine import effects as _fx
                    _fx.refresh_tokens(player)
                    return jsonify({"ok": True, "state": _build_state()})

        # --- Single-displacement path (non-weapon slots, or single-weapon swap) ---
        if force or to_pack:
            slot_map = {
                "helmet": player.helmets,
                "chest":  player.chest_armor,
                "legs":   player.leg_armor,
                "weapon": player.weapons,
            }
            existing_list = slot_map.get(item.slot.value, [])
            if existing_list:
                displaced = existing_list[0]
                if to_pack:
                    if player.pack_slots_used - 1 >= player.pack_size:
                        if discard_pack_index >= 0:
                            evicted_pack_item = player.pack[discard_pack_index] if equip_displaced else None
                            player.evict_pack_slot(discard_pack_index)
                        else:
                            pack_data = [{"name": p.name, "card_image": _item_card_image(p),
                                          "is_consumable": p.slot.value == "consumable"} for p in player.pack]
                            return jsonify({"error": "pack_full", "pack": pack_data,
                                            "displaced_name": displaced.name})
                    else:
                        evicted_pack_item = None
                    player.unequip(displaced)
                    try:
                        pi = player.pack.index(item)
                    except ValueError:
                        pi = pack_index
                    player.pack.pop(pi)
                    player.pack.insert(min(pi, len(player.pack)), displaced)
                    player.equip(item)
                    if equip_displaced and evicted_pack_item is not None:
                        if player.can_equip(evicted_pack_item):
                            player.equip(evicted_pack_item)
                        else:
                            player.pack.append(evicted_pack_item)
                    from werblers_engine import effects as _fx
                    _fx.refresh_tokens(player)
                    return jsonify({"ok": True, "state": _build_state()})
                else:
                    player.unequip(displaced)
        if not player.can_equip(item):
            return jsonify({"error": f"Cannot equip {item.name} \u2014 no free slot"}), 400
    player.pack.pop(pack_index)
    player.equip(item)
    return jsonify({"ok": True, "state": _build_state()})

@app.route("/api/manage_item", methods=["POST"])
def api_manage_item():
    """Discard or move-to-pack an equipped or packed item from the player sheet.

    JSON body:
        action  : "discard" | "to_pack" | "to_equip"
        source  : "equip_helmet" | "equip_chest" | "equip_leg" | "equip_weapon" | "pack"
        index   : integer index within that slot list
    """
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    action = data.get("action", "")
    source = data.get("source", "")
    idx    = int(data.get("index", 0))
    player = _game.current_player

    slot_map = {
        "equip_helmet": player.helmets,
        "equip_chest":  player.chest_armor,
        "equip_leg":    player.leg_armor,
        "equip_weapon": player.weapons,
        "pack":         player.pack,
    }
    item_list = slot_map.get(source)
    if item_list is None:
        return jsonify({"error": f"Unknown source: {source}"}), 400
    if idx < 0 or idx >= len(item_list):
        return jsonify({"error": "Index out of range"}), 400

    item = item_list[idx]

    if action == "discard":
        if source == "pack":
            player.pack.pop(idx)
        else:
            player.unequip(item)
        from werblers_engine import effects as _fx
        _fx.refresh_tokens(player)
        return jsonify({"ok": True, "state": _build_state()})

    if action == "to_pack":
        if source == "pack":
            return jsonify({"error": "Already in pack"}), 400
        discard_pack_idx = data.get("discard_pack_index")
        swap_to_equip = bool(data.get("swap_to_equip", False))
        if discard_pack_idx is not None:
            # User explicitly chose a slot to replace
            dpi = int(discard_pack_idx)
            if 0 <= dpi < len(player.pack):
                displaced_item = player.pack.pop(dpi)
            else:
                return jsonify({"error": "Invalid pack discard index"}), 400
        elif player.pack_slots_free <= 0:
            return jsonify({"error": "pack_full", "pack": [_ser_item(i) for i in player.pack]}), 409
        else:
            displaced_item = None
        player.unequip(item)
        player.pack.append(item)
        if swap_to_equip and displaced_item is not None:
            player.equip(displaced_item)
        from werblers_engine import effects as _fx
        _fx.refresh_tokens(player)
        return jsonify({"ok": True, "state": _build_state()})

    if action == "to_equip":
        if source != "pack":
            return jsonify({"error": "Item must come from pack to equip"}), 400
        if not player.can_equip(item):
            return jsonify({"error": f"Cannot equip {item.name} — no free slot"}), 400
        player.pack.pop(idx)
        player.equip(item)
        return jsonify({"ok": True, "state": _build_state()})

    return jsonify({"error": f"Unknown action: {action}"}), 400

@app.route("/api/discard_consumable", methods=["POST"])
def api_discard_consumable():
    """Discard a consumable from the player's consumables list."""
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("consumable_index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.consumables):
        return jsonify({"error": "Invalid consumable index"}), 400
    player.consumables.pop(idx)
    return jsonify({"ok": True, "state": _build_state()})

@app.route("/api/use_pack_consumable", methods=["POST"])
def api_use_pack_consumable():
    """Use a consumable item that is still in the player's pack (is_consumable=True).

    Looks up the Consumable definition by the item's name, removes the item from
    pack, and delegates to the same effect logic as /api/use_consumable for
    overworld effects.  Combat-only effects are not supported this way.

    JSON body:
        pack_index       : int  (index in player.pack)
        target_player_id : int  (optional, for give_curse)
    """
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    import copy as _copy
    data: dict = request.get_json(force=True) or {}
    pack_idx = int(data.get("pack_index", 0))
    player = _game.current_player
    if pack_idx < 0 or pack_idx >= len(player.pack):
        return jsonify({"error": "Invalid pack index"}), 400
    item = player.pack[pack_idx]
    if not item.is_consumable:
        return jsonify({"error": "That item is not a consumable"}), 400
    consumable = next((c for c in C.CONSUMABLE_POOL if c.name == item.name), None)
    if consumable is None:
        return jsonify({"error": f"Unknown consumable type: {item.name}"}), 400
    consumable = _copy.copy(consumable)
    # Remove from pack
    player.pack.pop(pack_idx)

    if consumable.effect_id == "gain_trait":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Tier-{tier} monster deck is empty."}), 400
        trait = (C.trait_for_monster(drawn) if drawn.trait_name else _game.trait_deck.draw())
        if trait is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": "No traits available."}), 400
        trait_log: list[str] = [f"{player.name} used {consumable.name}: drew {drawn.name}.",
                                 f"{player.name} gained trait '{trait.name}'!"]
        player.traits.append(trait)
        trait_items, trait_minions = _fx.on_trait_gained(player, trait, trait_log)
        player.pending_trait_items.extend(trait_items)
        player.pending_trait_minions.extend(trait_minions)
        _fx.refresh_tokens(player)
        _last_log = trait_log
        return jsonify({"ok": True, "phase": "trait_gained", "trait_name": trait.name,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "trait_desc": C.TRAIT_DESCRIPTIONS.get(trait.name, ""),
                        "state": _build_state()})

    elif consumable.effect_id == "give_curse":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": f"Tier-{tier} monster deck is empty."}), 400
        curse = (C.curse_for_monster(drawn) if drawn.curse_name else _game.curse_deck.draw())
        if curse is None:
            player.pack.insert(pack_idx, item)
            return jsonify({"error": "No curses available."}), 400
        target_id = data.get("target_player_id", None)
        all_players = _game.players
        if target_id is not None:
            chosen_target = next((p for p in all_players if p.player_id == int(target_id)), None)
            target = chosen_target if chosen_target else (all_players[0] if all_players else player)
        else:
            others = [p for p in all_players if p is not player]
            target = others[0] if others else player
        curse_log = [f"{player.name} used {consumable.name}: drew {drawn.name}.",
                     f"{target.name} received curse '{curse.name}'!"]
        target.curses.append(curse)
        _fx.on_curse_gained(target, curse, curse_log, None, [p for p in _game.players if p is not target], None)
        _fx.refresh_tokens(target)
        _last_log = curse_log
        return jsonify({"ok": True, "phase": "curse_given", "curse_name": curse.name,
                        "target_name": target.name, "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "curse_desc": C.CURSE_DESCRIPTIONS.get(curse.name, ""),
                        "state": _build_state()})

    player.pack.insert(pack_idx, item)
    return jsonify({"error": f"Unsupported consumable effect: {consumable.effect_id}"}), 400

@app.route("/api/use_consumable", methods=["POST"])
def api_use_consumable():
    """Use a consumable.

    Combat-only effects (strength_bonus, monster_str_mod, capture_monster) require
    an active pre-fight phase.  Overworld effects (gain_trait, give_curse) work
    at any time.
    """
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("consumable_index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.consumables):
        return jsonify({"error": "Invalid consumable index"}), 400
    consumable = player.consumables.pop(idx)

    # ------------------------------------------------------------------ COMBAT-ONLY
    if consumable.effect_id == "capture_monster":
        if _game._pending_combat is None:
            # Outside combat: use the device to START a fight with a tier-appropriate monster
            tier = consumable.effect_tier
            deck = _game.monster_decks.get(tier)
            if deck is None:
                player.consumables.insert(idx, consumable)
                return jsonify({"error": f"Invalid tier {tier}"}), 400
            monster = deck.draw()
            if monster is None:
                player.consumables.insert(idx, consumable)
                return jsonify({"error": f"Tier-{tier} monster deck is empty \u2014 no monster to summon."}), 400
            # Capture device is consumed to summon the fight
            log = [f"{player.name} activates {consumable.name}: a {monster.name} appears!"]
            other_players = [p for p in _game.players if p is not player]
            has_reroll = any(t.effect_id in ("ill_come_in_again", "i_see_everything") for t in player.traits)
            _game._prefight_str_bonus = 0
            _game._prefight_monster_str_bonus = 0
            _game._pending_combat = {
                "monster": monster,
                "effective_deck": deck,
                "other_players": other_players,
                "level": tier,
                "log": log,
                "old_pos": player.position,
                "new_pos": player.position,
                "card_value": 0,
                "tile_type": "MONSTER",
                "ill_come_in_again_available": has_reroll,
                "capture_device_triggered": True,  # marks this as device-initiated
            }
            combat_info = {
                "monster_name": monster.name,
                "monster_strength": monster.strength,
                "player_strength": player.combat_strength(),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "monster",
                "level": tier,
                "result": None,
                "ill_come_in_again_available": has_reroll,
            }
            _game._last_combat_info = combat_info
            _last_log = log
            return jsonify({"ok": True, "phase": "combat", "state": _build_state(),
                            "combat_info": _enrich_combat_info(combat_info)})
        # During combat: capture the current monster
        pc = _game._pending_combat
        monster = pc.get("monster") if pc else None
        if monster is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No monster to capture"}), 400
        if consumable.effect_tier < monster.level:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Capture device Tier {consumable.effect_tier} is too weak for a Level {monster.level} monster"}), 400
        if not player.add_captured_monster(monster):
            # The consumable was just removed (freeing its pack slot), so the
            # captured monster always takes that same slot — bypass the size check.
            player.captured_monsters.append(monster)
        log = pc["log"]
        log.append(f"  {consumable.name}: {monster.name} captured!")
        _game._pending_combat = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _last_log = log
        return jsonify({"ok": True, "phase": "captured", "monster_name": monster.name, "state": _build_state()})

    if consumable.effect_id == "" and consumable.strength_bonus > 0:
        if _game._pending_combat is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "Strength potions can only be used before a fight."}), 400
        _game._prefight_str_bonus += consumable.strength_bonus

    elif consumable.effect_id == "monster_str_mod":
        if _game._pending_combat is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "Monster-weakening vials can only be used before a fight."}), 400
        _game._prefight_monster_str_bonus += consumable.effect_value

    # ------------------------------------------------------------------ OVERWORLD: gain_trait
    elif consumable.effect_id == "gain_trait":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Tier-{tier} monster deck is empty — no effect."}), 400
        trait = (
            C.trait_for_monster(drawn) if drawn.trait_name
            else _game.trait_deck.draw()
        )
        if trait is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No traits available."}), 400
        trait_log: list[str] = []
        player.traits.append(trait)
        trait_log.append(f"{player.name} used {consumable.name}: drew {drawn.name}.")
        trait_log.append(f"{player.name} gained trait '{trait.name}'!")
        trait_items, trait_minions = _fx.on_trait_gained(player, trait, trait_log)
        player.pending_trait_items.extend(trait_items)
        player.pending_trait_minions.extend(trait_minions)
        _fx.refresh_tokens(player)
        _last_log = trait_log
        return jsonify({"ok": True, "phase": "trait_gained", "trait_name": trait.name,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "trait_desc": C.TRAIT_DESCRIPTIONS.get(trait.name, ""),
                        "state": _build_state()})

    # ------------------------------------------------------------------ OVERWORLD: give_curse
    elif consumable.effect_id == "give_curse":
        tier = consumable.effect_tier
        deck = _game.monster_decks.get(tier)
        if deck is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Invalid tier {tier}"}), 400
        drawn = deck.draw()
        if drawn is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Tier-{tier} monster deck is empty — no effect."}), 400
        curse = (
            C.curse_for_monster(drawn) if drawn.curse_name
            else _game.curse_deck.draw()
        )
        if curse is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No curses available."}), 400
        # Target: chosen by client — can be any player including self
        target_id = data.get("target_player_id", None)
        all_players = _game.players
        if target_id is not None:
            chosen_target = next((p for p in all_players if p.player_id == int(target_id)), None)
            target = chosen_target if chosen_target else (all_players[0] if all_players else player)
        else:
            others = [p for p in all_players if p is not player]
            target = others[0] if others else player
        curse_log: list[str] = []
        curse_log.append(f"{player.name} used {consumable.name}: drew {drawn.name}.")
        target.curses.append(curse)
        curse_log.append(f"{target.name} received curse '{curse.name}'!")
        _fx.on_curse_gained(target, curse, curse_log, None, [p for p in _game.players if p is not target], None)
        _fx.refresh_tokens(target)
        _last_log = curse_log
        return jsonify({"ok": True, "phase": "curse_given", "curse_name": curse.name,
                        "target_name": target.name,
                        "monster_name": drawn.name,
                        "monster_card_image": _monster_card_image(drawn.name),
                        "curse_desc": C.CURSE_DESCRIPTIONS.get(curse.name, ""),
                        "state": _build_state()})

    # ------------------------------------------------------------------ Combat info update
    # (only reached for the combat-only strength effects above)
    ability_mod = _game._last_combat_info.get("ability_player_mod", 0) if _game._last_combat_info else 0
    if _game._last_combat_info:
        _game._last_combat_info["player_strength"] = player.combat_strength() + _game._prefight_str_bonus + ability_mod
        _game._last_combat_info["monster_strength"] = (
            _game._last_combat_info.get("monster_strength", 0)
            + (consumable.effect_value if consumable.effect_id == "monster_str_mod" else 0)
        )
        _game._last_combat_info["prefight_str_bonus"] = _game._prefight_str_bonus
    return jsonify({"ok": True, "state": _build_state(), "combat_info": _enrich_combat_info(dict(_game._last_combat_info)) if _game._last_combat_info else None})

@app.route("/api/bystander_consumable", methods=["POST"])
def api_bystander_consumable():
    """Non-fighting nearby player uses (or skips) a consumable at combat start.

    Body: {player_id: int, consumable_index: int | null, skip: bool}
    The caller must be in the nearby_queue list of the pending combat.
    """
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    if _game._pending_combat is None:
        return jsonify({"error": "No pending combat"}), 400
    data: dict = request.get_json(force=True) or {}
    bystander_id = int(data.get("player_id", -1))
    skip: bool = bool(data.get("skip", False))
    consumable_index = data.get("consumable_index", None)

    bystander = next((p for p in _game.players if p.player_id == bystander_id), None)
    if bystander is None:
        return jsonify({"error": f"Unknown player_id {bystander_id}"}), 400

    pc = _game._pending_combat
    nearby_queue: list = pc.get("nearby_queue", [])
    if bystander_id not in nearby_queue:
        return jsonify({"error": "Player is not in the nearby queue"}), 400

    # Remove from queue regardless of action
    nearby_queue.remove(bystander_id)
    pc["nearby_queue"] = nearby_queue

    log = pc.get("log", [])

    if not skip and consumable_index is not None:
        cidx = int(consumable_index)
        # Only monster_str_mod consumables are allowed for bystanders
        usable = [c for c in bystander.consumables if c.effect_id == "monster_str_mod"]
        if 0 <= cidx < len(usable):
            chosen = usable[cidx]
            bystander.consumables.remove(chosen)
            monster = pc.get("monster")
            if monster:
                delta = chosen.effect_value
                old_str = monster.strength
                monster.strength = max(0, monster.strength + delta)
                sign = "+" if delta >= 0 else ""
                log.append(
                    f"  {bystander.name} used {chosen.name} on {monster.name}: "
                    f"monster strength {sign}{delta} ({old_str} \u2192 {monster.strength})."
                )
                # Update cached combat info
                if _game._last_combat_info:
                    _game._last_combat_info["monster_strength"] = monster.strength

    _last_log = log

    # Return updated combat info with remaining queue
    combat_info = _enrich_combat_info(dict(_game._last_combat_info)) if _game._last_combat_info else None
    if combat_info is not None:
        # Rebuild nearby_queue list for the response
        remaining_players = [p for p in _game.players
                             if p.player_id in nearby_queue]
        combat_info["nearby_queue"] = [
            {
                "player_id":   bp.player_id,
                "name":        bp.name,
                "token_image": _TOKEN_MAP.get(bp.hero.id.name if bp.hero else "", ""),
                "consumables": [{"name": c.name, "card_image": _consumable_card_image(c.name),
                                 "effect_id": c.effect_id, "effect_value": c.effect_value,
                                 "effect_tier": c.effect_tier, "strength_bonus": c.strength_bonus}
                                for c in bp.consumables if c.effect_id == "monster_str_mod"],
            }
            for bp in remaining_players
        ]
    return jsonify({"ok": True, "combat_info": combat_info, "state": _build_state()})

@app.route("/api/swiftness_flee", methods=["POST"])
def api_swiftness_flee():
    """Swiftness trait: flee from pending monster/miniboss at no cost (no position change)."""
    global _last_log
    try:
        if _game is None:
            return jsonify({"error": "No game in progress"}), 400
        if _game._pending_combat is None:
            return jsonify({"error": "No pending combat"}), 400
        player = _game.current_player
        if not any(t.effect_id == "swiftness" for t in player.traits):
            return jsonify({"error": "Player does not have Swiftness"}), 400
        pc = _game._pending_combat
        if pc.get("type", "monster") == "werbler":
            return jsonify({"error": "Cannot flee from the Werbler!"}), 400
        _game._pending_combat = None
        log = pc["log"]
        monster = pc.get("monster")
        if monster:
            log.append(f"  Swiftness: {player.name} flees from {monster.name}! No combat.")
        _game._prefight_str_bonus = 0
        _game._prefight_monster_str_bonus = 0
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        _last_log = log
        return jsonify({"phase": "done", "state": _build_state()})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {exc}"}), 500


@app.route("/api/flee", methods=["POST"])
def api_flee():
    """Billfold: Fly, you dummy! — flee the pending monster or miniboss combat."""
    global _last_log
    try:
        if _game is None:
            return jsonify({"error": "No game in progress"}), 400
        result = _game.flee_monster()
        if "error" in result:
            return jsonify(result), 400
        _last_log = result.get("log", [])
        return jsonify({"phase": "done", "state": _build_state()})
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        traceback.print_exc()
        return jsonify({"error": f"Server error during flee: {exc}\n\nTraceback:\n{tb}"}), 500


@app.route("/api/fight", methods=["POST"])
def api_fight():
    """Resolve the pending monster combat."""
    global _last_log
    try:
        if _game is None:
            return jsonify({"error": "No game in progress"}), 400
        if _game._pending_combat is None:
            return jsonify({"error": "No pending combat"}), 400
        from_mystery = _game._pending_combat.get("from_mystery", False)
        result = _game.fight()
        _last_log = result.get("log", [])
        combat_info = result.get("combat_info")
        if combat_info:
            combat_info = _enrich_combat_info(combat_info)
        phase = "summoned_done" if result.get("summoned_monster") else "done"
        return jsonify({"phase": phase, "state": _build_state(), "combat_info": combat_info})
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        traceback.print_exc()
        return jsonify({"error": f"Server error during fight: {exc}\n\nTraceback:\n{tb}"}), 500

@app.route("/api/use_eight_lives", methods=["POST"])
def api_use_eight_lives():
    """Immediately use Eight Lives to remove a curse."""
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    curse_index = int(data.get("curse_index", 0))
    result = _game.use_eight_lives(curse_index)
    if result.get("log"):
        _last_log = _last_log + result["log"]
    return jsonify({"ok": result["ok"], "state": _build_state()})

@app.route("/api/place_trait_item", methods=["POST"])
def api_place_trait_item():
    """Place a pending trait item (received from a trait like Ball and Chain).

    JSON body:
        placement_choices : same placement dict as resolve_offer uses
        player_id         : optional, target a specific player (for Rake It In after turn advance)
    """
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    target_pid = data.get("player_id")
    if target_pid is not None:
        player = next((p for p in _game.players if p.player_id == target_pid), None)
        if player is None:
            return jsonify({"error": "Unknown player_id"}), 400
    else:
        player = _game.current_player
    if not player.pending_trait_items:
        return jsonify({"error": "No pending trait items"}), 400
    item = player.pending_trait_items.pop(0)
    choices = data.get("placement_choices", {})
    log: list[str] = []
    if choices.get("discard"):
        log.append(f"  {item.name} discarded.")
    else:
        _game._apply_item_to_player(player, item, choices, log)
    from werblers_engine import effects as _fx
    _fx.refresh_tokens(player)
    return jsonify({"ok": True, "state": _build_state(), "log": log})

@app.route("/api/release_monster", methods=["POST"])
def api_release_monster():
    """Release a captured monster from the player's pack."""
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.captured_monsters):
        return jsonify({"error": "Invalid monster index"}), 400
    player.captured_monsters.pop(idx)
    return jsonify({"ok": True, "state": _build_state()})

@app.route("/api/summon_monster", methods=["POST"])
def api_summon_monster():
    """Summon a captured monster as an ENEMY, triggering a fight."""
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.captured_monsters):
        return jsonify({"error": "Invalid monster index"}), 400
    monster = player.captured_monsters.pop(idx)
    # Set up a pending combat with this monster as the enemy
    tier = monster.level
    log = [f"{player.name} summons {monster.name} to fight!"]
    other_players = [p for p in _game.players if p is not player]
    has_reroll = any(t.effect_id in ("ill_come_in_again", "i_see_everything") for t in player.traits)
    _game._prefight_str_bonus = 0
    _game._prefight_monster_str_bonus = 0
    _game._pending_combat = {
        "monster": monster,
        "effective_deck": _game.monster_decks.get(tier),
        "other_players": other_players,
        "level": tier,
        "log": log,
        "old_pos": player.position,
        "new_pos": player.position,
        "card_value": 0,
        "tile_type": "MONSTER",
        "ill_come_in_again_available": has_reroll,
        "summoned_monster": True,
    }
    _male_bonus = monster.bonus_vs_male if (monster.bonus_vs_male and player.hero and player.hero.is_male) else 0
    combat_info = {
        "monster_name": monster.name,
        "monster_strength": monster.strength + _male_bonus,
        "monster_bonus_vs_male": _male_bonus,
        "player_strength": player.combat_strength(),
        "player_id": player.player_id,
        "player_name": player.name,
        "hero_id": player.hero.id.name if player.hero else None,
        "category": "monster",
        "level": tier,
        "result": None,
        "ill_come_in_again_available": has_reroll,
    }
    _game._last_combat_info = combat_info
    _last_log = log
    return jsonify({"ok": True, "phase": "combat", "state": _build_state(),
                    "combat_info": _enrich_combat_info(combat_info)})


# ------------------------------------------------------------------
# Resolve pending minion replacement (6-slot cap)
# ------------------------------------------------------------------
@app.route("/api/resolve_minion", methods=["POST"])
def api_resolve_minion():
    """Replace an existing minion with a pending one, or discard the pending minion."""
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    player_id: int = int(data.get("player_id", _game.current_player.player_id))
    replace_index: int = int(data.get("replace_index", -1))
    discard: bool = bool(data.get("discard", False))

    player = next((p for p in _game.players if p.player_id == player_id), None)
    if player is None:
        return jsonify({"error": "Player not found"}), 400
    if not player.pending_trait_minions:
        return jsonify({"error": "No pending minions"}), 400

    minion = player.pending_trait_minions.pop(0)
    log: list[str] = []
    if discard:
        log.append(f"  {minion.name} discarded (minion slots full).")
    elif 0 <= replace_index < len(player.minions):
        old = player.minions[replace_index]
        player.minions[replace_index] = minion
        from werblers_engine import effects as _fx_mod
        _fx_mod.on_minion_gained(player, minion, log)
        log.append(f"  {old.name} replaced by {minion.name}.")
    else:
        # Try adding normally (shouldn't happen at cap, but just in case)
        if not player.add_minion(minion):
            player.pending_trait_minions.insert(0, minion)
            return jsonify({"error": "Invalid replace_index and at minion cap"}), 400
        from werblers_engine import effects as _fx_mod
        _fx_mod.on_minion_gained(player, minion, log)
        log.append(f"  {minion.name} added to minions.")

    _last_log = log
    return jsonify({"ok": True, "state": _build_state()})


# ------------------------------------------------------------------
# Legacy single-call endpoint (still works for tests/old clients)
# ------------------------------------------------------------------
@app.route("/api/play_turn", methods=["POST"])
def api_play_turn():
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    card_index: int = data.get("card_index", 0)
    flee: bool = bool(data.get("flee", False))
    shop_choice: int = data.get("shop_choice", 0)
    result = _game.play_turn(card_index=card_index, flee=flee, shop_choice=shop_choice)
    _last_log = result.encounter_log
    return jsonify({"ok": True, "state": _build_state()})
# ---------------------------------------------------------------------------
# State serialisation helpers
# ---------------------------------------------------------------------------
def _tile_image(tile, is_night: bool, mb1_defeated: bool = False, mb2_defeated: bool = False) -> str:
    # Tile 1 (START) always shows as a blank tile regardless of night or state
    if tile.index == 1:
        return "Tiles/Blank Tile.png"
    # Special tiles always show their real image regardless of time or reveal state
    if tile.tile_type == TileType.DAY_NIGHT:
        return "Tiles/Day and Night Tile.png"
    if tile.tile_type == TileType.WERBLER:
        return "Tiles/Werbler Tile.png"
    if tile.tile_type == TileType.MINIBOSS:
        if tile.index == 30:
            return "Tiles/Mini Boss 1 Defeated.png" if mb1_defeated else "Tiles/Mini Boss 1.png"
        else:
            return "Tiles/Mini Boss 2 Defeated.png" if mb2_defeated else "Tiles/Mini Boss 2 Tile.png"
    # At night all other squares show Night Tile (revealed or not)
    if is_night:
        return "Tiles/Night Tile.png"
    # During day: unrevealed tiles show Hidden
    if not tile.revealed:
        return "Tiles/Hidden Tile.png"
    # Revealed daytime tiles show their type
    mapping = {
        TileType.BLANK:     "Tiles/Blank Tile.png",
        TileType.MONSTER:   "Tiles/Monster Tile.png",
        TileType.CHEST:     "Tiles/Chest Tile.png",
        TileType.SHOP:      "Tiles/Shop Tile.jpg",
        TileType.MYSTERY:   "Tiles/Mystery Tile.png",
    }
    return mapping.get(tile.tile_type, "Tiles/Hidden Tile.png")
_SLOT_IMG_FOLDER = {
    "helmet": "Items/Head Armour/Head Armour Finished Cards",
    "chest":  "Items/Chest Armour/Chest Armour Finished Cards",
    "legs":   "Items/Leg Armour/Leg Armour Finished Cards",
    "weapon": "Items/Weapons/Weapon Finished Cards",
}
_ITEM_FILENAME_OVERRIDES: dict[str, str] = {
    # Game data uses "Swiss Guard Helmet" (no apostrophe) but the card file is named with one
    "Swiss Guard Helmet": "Swiss Guard's Helmet",
    # Game data uses "Pumped Up Kicks" (capital U) but files use "Pumped up Kicks"
    "Pumped Up Kicks": "Pumped up Kicks",
    # Card file uses abbreviated name
    "Chestplate Made of What the Black Box is Made of": "Black Box Chestplate",
    # Game data uses lowercase 'b' but card file uses capital B
    "Sweet bandana": "Sweet Bandana",
}

def _normalize_item_filename(name: str) -> str:
    """Replace curly/smart apostrophes with straight ones so filenames match disk."""
    return name.replace('\u2019', "'").replace('\u2018', "'")

def _item_card_image(item) -> str:
    if item.slot.value == "consumable":
        return _consumable_card_image(item.name)
    folder = _SLOT_IMG_FOLDER.get(item.slot.value, "")
    display = _ITEM_FILENAME_OVERRIDES.get(item.name, _normalize_item_filename(item.name))
    return f"{folder}/{display} Card.png" if folder else ""

def _item_card_image_from_dict(item_dict: dict) -> str:
    slot = item_dict.get("slot", "")
    name = item_dict.get("name", "")
    if slot == "consumable":
        return _consumable_card_image(name)
    folder = _SLOT_IMG_FOLDER.get(slot, "")
    display = _ITEM_FILENAME_OVERRIDES.get(name, _normalize_item_filename(name))
    return f"{folder}/{display} Card.png" if folder else ""

def _tile_level(pos: int) -> int:
    if pos <= 30: return 1
    if pos <= 60: return 2
    return 3
def _consumable_card_image(name: str) -> str:
    # Normalize curly apostrophes to straight for filesystem path matching
    safe_name = name.replace('\u2019', "'").replace('\u2018', "'")
    return f"Items/Consumables/Consumable Finished Cards/{safe_name} Card.png"
def _monster_card_image(name: str) -> str:
    return f"Monsters/Finished Cards/{name} Card.png"

def _minion_card_image(name: str) -> str:
    return f"Minions/Finished Minion Cards/{name} Card.png"

def _miniboss_card_image(name: str) -> str:
    return f"Mini Bosses/Finished Cards/{name} Card.png"

def _werbler_card_image(name: str) -> str:
    return f"Werblers/Werbler Finished Cards/{name} Card.png"

def _enrich_combat_info(info: dict) -> dict:
    """Add card image path and player gear to combat info for the frontend battle scene."""
    category = info.get("category", "monster")
    name = info.get("monster_name", "")
    if category == "miniboss":
        info["card_image"] = _miniboss_card_image(name)
    elif category == "werbler":
        info["card_image"] = _werbler_card_image(name)
    else:
        info["card_image"] = _monster_card_image(name)
    bg_map = {1: "Backgrounds/Forest Background.png", 2: "Backgrounds/Cave Background.png", 3: "Backgrounds/Dungeon Background.png"}
    info["background"] = bg_map.get(info.get("level", 1), bg_map[1])
    # Add hero card image for the fighting player
    hero_id = info.get("hero_id")
    if hero_id:
        info["hero_card_image"] = _CARD_IMG_MAP.get(hero_id, "")
        info["hero_animations"] = _HERO_ANIM_MAP.get(hero_id, {})
    # Add swiftness flag for pre-fight flee button
    if _game is not None:
        _pfp = _game.current_player
        info["has_swiftness"] = any(t.effect_id == "swiftness" for t in _pfp.traits)
    # Add descriptions for trait/curse gained
    trait_name = info.get("trait_gained")
    if trait_name:
        info["trait_gained_desc"] = C.TRAIT_DESCRIPTIONS.get(trait_name, "")
    curse_name = info.get("curse_gained")
    if curse_name:
        info["curse_gained_desc"] = C.CURSE_DESCRIPTIONS.get(curse_name, "")
    # Attach player gear, traits, and curses for the battle display
    if _game is not None:
        player_id = info.get("player_id")
        player = next((p for p in _game.players if p.player_id == player_id), None)
        if player is None:
            player = _game.current_player
        info["player_gear"] = (
            [_ser_item(i) for i in player.helmets]
            + [_ser_item(i) for i in player.chest_armor]
            + [_ser_item(i) for i in player.leg_armor]
            + [_ser_item(i) for i in player.weapons]
        )
        info["player_traits"] = [_ser_trait(t) for t in player.traits]
        info["player_curses"] = [_ser_curse(c) for c in player.curses]
        # Compute nearby-player bystander queue (within 5 tiles, has combat consumables)
        if "nearby_queue" not in info and _game._pending_combat is not None:
            _PROXIMITY = 5
            other_players = _game._pending_combat.get("other_players", [])
            queue = []
            for bp in other_players:
                if abs(bp.position - player.position) > _PROXIMITY:
                    continue
                usable = [c for c in bp.consumables if c.effect_id == "monster_str_mod"]
                if not usable:
                    continue
                queue.append({
                    "player_id":   bp.player_id,
                    "name":        bp.name,
                    "token_image": _TOKEN_MAP.get(bp.hero.id.name if bp.hero else "", ""),
                    "consumables": [{"name": c.name, "card_image": _consumable_card_image(c.name),
                                     "effect_id": c.effect_id, "effect_value": c.effect_value,
                                     "effect_tier": c.effect_tier, "strength_bonus": c.strength_bonus}
                                    for c in usable],
                })
            info["nearby_queue"] = queue
            # Persist queue in pending_combat for the bystander endpoint
            if _game._pending_combat is not None:
                _game._pending_combat["nearby_queue"] = [q["player_id"] for q in queue]
        info["player_minions"] = [{"name": m.name, "strength_bonus": m.strength_bonus, "card_image": _minion_card_image(m.name)} for m in player.minions]
        info["player_base_strength"] = player.base_strength
        info["player_helmet_slots"] = player.helmet_slots
        info["player_chest_slots"] = player.chest_slots
        info["player_legs_slots"] = player.legs_slots
        info["player_weapon_hands"] = player.weapon_hands
        info.setdefault("prefight_str_bonus", _game._prefight_str_bonus)
        # Add hero passive ability bonuses to ability_breakdown for hover tooltip
        _hero_breakdown = list(info.get("ability_breakdown") or [])
        hero = player.hero
        is_night = _game.is_night
        if hero:
            if hero.has_luscious_locks and not player.helmets:
                _hero_breakdown.insert(0, "Luscious Locks (no helmet): +5")
            if hero.has_skimpy_armour and player.chest_armor:
                # Skimpy armour: each chest piece contributes min 8
                for item in player.chest_armor:
                    skimpy_bonus = max(0, 8 - item.strength_bonus)
                    if skimpy_bonus > 0:
                        _hero_breakdown.insert(0, f"Skimpy Armour ({item.name}): +{skimpy_bonus} extra")
            if hero.has_night_stalker and is_night:
                _hero_breakdown.insert(0, f"Night Stalker (night): +{hero.night_stalker_bonus}")
        if _hero_breakdown:
            info["ability_breakdown"] = _hero_breakdown
    return info
def _ser_item(item) -> dict:
    if item.slot.value == "consumable":
        card_img = _consumable_card_image(item.name)
    else:
        card_img = _item_card_image(item)
    return {
        "name":           item.name,
        "slot":           item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id":      item.effect_id,
        "hands":          item.hands,
        "tokens":         item.tokens,
        "card_image":     card_img,
        "is_consumable":  item.is_consumable,
    }
def _ser_trait(t) -> dict:
    return {"name": t.name, "effect_id": t.effect_id, "tokens": t.tokens,
            "strength_bonus": t.strength_bonus,
            "description": C.TRAIT_DESCRIPTIONS.get(t.name, "")}
def _ser_curse(c) -> dict:
    return {"name": c.name, "effect_id": c.effect_id, "tokens": c.tokens,
            "strength_bonus": c.strength_bonus,
            "description": C.CURSE_DESCRIPTIONS.get(c.name, "")}
def _build_state() -> dict:
    g = _game
    current = g.current_player
    board_data = [
        {
            "index":     t.index,
            "tile_type": t.tile_type.name,
            "revealed":  t.revealed,
            "image":     _tile_image(t, g.is_night, mb1_defeated=False, mb2_defeated=False),
            "image_defeated": _tile_image(t, g.is_night, mb1_defeated=True, mb2_defeated=True) if t.tile_type == TileType.MINIBOSS else None,
        }
        for t in g.board[1:]
    ]
    players_data = []
    for p in g.players:
        hid = p.hero.id.name if p.hero else None
        players_data.append({
            "player_id":          p.player_id,
            "name":               p.name,
            "position":           p.position,
            "strength":           p.combat_strength(),
            "hero_id":            hid,
            "token_image":        _TOKEN_MAP.get(hid) if hid else None,
            "hero_card_image":    _CARD_IMG_MAP.get(hid) if hid else None,
            "hero_animations":    _HERO_ANIM_MAP.get(hid, {}) if hid else {},
            "movement_hand":      list(p.movement_hand),
            "is_current":         p is current,
            # Detailed equipment (with tokens for rendering +/-1 token badges)
            "helmets":            [_ser_item(i) for i in p.helmets],
            "chest_armor":        [_ser_item(i) for i in p.chest_armor],
            "leg_armor":          [_ser_item(i) for i in p.leg_armor],
            "weapons":            [_ser_item(i) for i in p.weapons],
            "pack":               [_ser_item(i) for i in p.pack],
            "consumables":        [{"name": c.name, "card_image": _consumable_card_image(c.name), "strength_bonus": c.strength_bonus, "effect_id": c.effect_id, "effect_tier": c.effect_tier, "effect_value": c.effect_value} for c in p.consumables],
            "captured_monsters":  [{"name": m.name, "card_image": _monster_card_image(m.name), "level": m.level} for m in p.captured_monsters],
            "traits":             [_ser_trait(t) for t in p.traits],
            "curses":             [_ser_curse(c) for c in p.curses],
            "minions":            [{"name": m.name, "strength_bonus": m.strength_bonus, "effect_id": m.effect_id, "card_image": _minion_card_image(m.name)} for m in p.minions],
            # Slot capacities (for the inventory popup)
            "helmet_slots":       p.helmet_slots,
            "chest_slots":        p.chest_slots,
            "legs_slots":         p.legs_slots,
            "pack_slots_free":    p.pack_slots_free,
            "pack_size":          p.pack_size,
            "miniboss1_defeated": p.miniboss1_defeated,
            "miniboss2_defeated": p.miniboss2_defeated,
            "base_strength":       p.base_strength,
            "weapon_hands":          p.weapon_hands,
            "movement_discard_top":   p.movement_discard[-1] if p.movement_discard else None,
            "movement_discard_count": len(p.movement_discard),
            "movement_discard_list":  list(p.movement_discard),
            "movement_deck_cards":    g.movement_decks[p.player_id].peek_all(),
            "movement_card_bonus":    p.hero.movement_card_bonus if p.hero else 0,
            "movement_card_bonus":    p.hero.movement_card_bonus if p.hero else 0,
            "pending_trait_items":    [_ser_item(i) for i in p.pending_trait_items],
            "pending_trait_minions": [{"name": m.name, "strength_bonus": m.strength_bonus, "effect_id": m.effect_id, "card_image": _minion_card_image(m.name)} for m in p.pending_trait_minions],
            "max_minions":           p.MAX_MINIONS,
            "beggar_gifts":          getattr(p, "_beggar_gifts", 0),
            "beggar_completed":      getattr(p, "_beggar_completed", False),
        })
    return {
        "turn_number":       g.turn_number,
        "is_night":          g.is_night,
        "current_player_id": current.player_id,
        "game_status":       g.status.name,
        "winner":            g.winner,
        "board":             board_data,
        "players":           players_data,
        "log":               _last_log,
        "has_pending_offer": g._pending_offer is not None,
        "has_pending_combat": g._pending_combat is not None and g._pending_combat.get("type") != "awaiting_charlie_work",
        "has_pending_charlie_work": g._pending_combat is not None and g._pending_combat.get("type") == "awaiting_charlie_work",
        "prefight_str_bonus": g._prefight_str_bonus,
        "prefight_monster_str_bonus": g._prefight_monster_str_bonus,
    }
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

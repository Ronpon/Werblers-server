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
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "Images")
MUSIC_DIR  = os.path.join(BASE_DIR, "Music")
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
    _pending_log = []
    _last_log = combined_log
    return jsonify({"phase": "done", "state": _build_state()})

@app.route("/api/equip_from_pack", methods=["POST"])
def api_equip_from_pack():
    """Move an item from pack to an equipment slot.
    
    Accepts optional ``force`` flag to discard the first currently equipped
    item in the target slot when no free slot is available.
    """
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    pack_index = int(data.get("pack_index", 0))
    force = bool(data.get("force", False))
    player = _game.current_player
    if pack_index < 0 or pack_index >= len(player.pack):
        return jsonify({"error": "Invalid pack index"}), 400
    item = player.pack[pack_index]
    if not player.can_equip(item):
        if force:
            slot_map = {
                "helmet": player.helmets,
                "chest":  player.chest_armor,
                "legs":   player.leg_armor,
                "weapon": player.weapons,
            }
            existing_list = slot_map.get(item.slot.value, [])
            if existing_list:
                player.unequip(existing_list[0])
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
        if player.pack_slots_free <= 0:
            return jsonify({"error": "Pack is full"}), 400
        player.unequip(item)
        player.pack.append(item)
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

@app.route("/api/use_consumable", methods=["POST"])
def api_use_consumable():
    """Use a consumable during the pre-fight phase.

    Removes the consumable from the player's list and, if it has a plain
    strength_bonus, stores it in _prefight_str_bonus so fight() can apply it.
    """
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    if _game._pending_combat is None:
        return jsonify({"error": "No pending combat — can only use consumables before a fight"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("consumable_index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.consumables):
        return jsonify({"error": "Invalid consumable index"}), 400
    consumable = player.consumables.pop(idx)
    if consumable.effect_id == "capture_monster":
        pc = _game._pending_combat
        monster = pc.get("monster") if pc else None
        if monster is None:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "No monster to capture"}), 400
        if consumable.effect_tier < monster.level:
            player.consumables.insert(idx, consumable)
            return jsonify({"error": f"Capture device Tier {consumable.effect_tier} is too weak for a Level {monster.level} monster"}), 400
        if not player.add_captured_monster(monster):
            player.consumables.insert(idx, consumable)
            return jsonify({"error": "Pack is full — cannot capture monster"}), 400
        log = pc["log"]
        log.append(f"  {consumable.name}: {monster.name} captured!")
        _game._pending_combat = None
        _game._finish_post_encounter(player, log)
        _game._advance_turn()
        global _last_log
        _last_log = log
        return jsonify({"ok": True, "phase": "captured", "monster_name": monster.name, "state": _build_state()})
    elif consumable.effect_id == "" and consumable.strength_bonus > 0:
        _game._prefight_str_bonus += consumable.strength_bonus
    elif consumable.effect_id == "monster_str_mod":
        _game._prefight_monster_str_bonus += consumable.effect_value
    # Update the stored combat_info to reflect new bonuses
    ability_mod = _game._last_combat_info.get("ability_player_mod", 0) if _game._last_combat_info else 0
    if _game._last_combat_info:
        _game._last_combat_info["player_strength"] = player.combat_strength() + _game._prefight_str_bonus + ability_mod
        _game._last_combat_info["monster_strength"] = (
            _game._last_combat_info.get("monster_strength", 0)
            + (consumable.effect_value if consumable.effect_id == "monster_str_mod" else 0)
        )
        _game._last_combat_info["prefight_str_bonus"] = _game._prefight_str_bonus
    return jsonify({"ok": True, "state": _build_state(), "combat_info": _enrich_combat_info(dict(_game._last_combat_info)) if _game._last_combat_info else None})

@app.route("/api/fight", methods=["POST"])
def api_fight():
    """Resolve the pending monster combat."""
    global _last_log
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    if _game._pending_combat is None:
        return jsonify({"error": "No pending combat"}), 400
    result = _game.fight()
    _last_log = result.get("log", [])
    combat_info = result.get("combat_info")
    if combat_info:
        combat_info = _enrich_combat_info(combat_info)
    return jsonify({"phase": "done", "state": _build_state(), "combat_info": combat_info})

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
    """Convert a captured monster into a minion."""
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data: dict = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    player = _game.current_player
    if idx < 0 or idx >= len(player.captured_monsters):
        return jsonify({"error": "Invalid monster index"}), 400
    from werblers_engine.types import Minion
    monster = player.captured_monsters.pop(idx)
    player.minions.append(Minion(name=monster.name, strength_bonus=monster.strength, effect_id=""))
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
    }
    return mapping.get(tile.tile_type, "Tiles/Hidden Tile.png")
_SLOT_IMG_FOLDER = {
    "helmet": "Items/Head Armour/Head Armour Finished Cards",
    "chest":  "Items/Chest Armour/Chest Armour Finished Cards",
    "legs":   "Items/Leg Armour/Leg Armour Finished Cards",
    "weapon": "Items/Weapons/Weapon Finished Cards",
}
def _item_card_image(item) -> str:
    if item.slot.value == "consumable":
        return _consumable_card_image(item.name)
    folder = _SLOT_IMG_FOLDER.get(item.slot.value, "")
    return f"{folder}/{item.name} Card.png" if folder else ""

def _item_card_image_from_dict(item_dict: dict) -> str:
    slot = item_dict.get("slot", "")
    name = item_dict.get("name", "")
    if slot == "consumable":
        return _consumable_card_image(name)
    folder = _SLOT_IMG_FOLDER.get(slot, "")
    return f"{folder}/{name} Card.png" if folder else ""

def _tile_level(pos: int) -> int:
    if pos <= 30: return 1
    if pos <= 60: return 2
    return 3
def _consumable_card_image(name: str) -> str:
    return f"Items/Consumables/Consumable Finished Cards/{name} Card.png"
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
            "description": C.TRAIT_DESCRIPTIONS.get(t.name, "")}
def _ser_curse(c) -> dict:
    return {"name": c.name, "effect_id": c.effect_id, "tokens": c.tokens,
            "description": C.CURSE_DESCRIPTIONS.get(c.name, "")}
def _build_state() -> dict:
    g = _game
    current = g.current_player
    mb1_defeated = any(p.miniboss1_defeated for p in g.players)
    mb2_defeated = any(p.miniboss2_defeated for p in g.players)
    board_data = [
        {
            "index":     t.index,
            "tile_type": t.tile_type.name,
            "revealed":  t.revealed,
            "image":     _tile_image(t, g.is_night, mb1_defeated, mb2_defeated),
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
            "movement_hand":      list(p.movement_hand),
            "is_current":         p is current,
            # Detailed equipment (with tokens for rendering +/-1 token badges)
            "helmets":            [_ser_item(i) for i in p.helmets],
            "chest_armor":        [_ser_item(i) for i in p.chest_armor],
            "leg_armor":          [_ser_item(i) for i in p.leg_armor],
            "weapons":            [_ser_item(i) for i in p.weapons],
            "pack":               [_ser_item(i) for i in p.pack],
            "consumables":        [{"name": c.name, "card_image": _consumable_card_image(c.name), "strength_bonus": c.strength_bonus, "effect_id": c.effect_id, "effect_tier": c.effect_tier} for c in p.consumables],
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
            "weapon_hands":          p.weapon_hands,
            "movement_discard_top":   p.movement_discard[-1] if p.movement_discard else None,
            "movement_discard_count": len(p.movement_discard),
            "movement_discard_list":  list(p.movement_discard),
            "movement_deck_cards":    g.movement_decks[p.player_id].peek_all(),
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

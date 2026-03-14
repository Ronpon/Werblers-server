"""Script to write the correct complete game.py and encounters.py."""
import pathlib

GAME_PY = '''"""Game orchestrator — ties board, player, decks, and encounters together.

Supports 1-4 players in competitive mode with fixed turn rotation.
"""

from __future__ import annotations

from typing import Callable, Optional

from .types import (
    CombatResult,
    GameStatus,
    Tile,
    TileType,
    TurnResult,
    Item,
    Monster,
    Trait,
    Curse,
)
from .board import generate_board, get_level
from .player import Player
from .deck import Deck
from .heroes import Hero, HeroId, HEROES
from . import content as C
from . import encounters as enc
from . import effects as _fx


class Game:
    """Top-level game state machine for Werblers (1-4 players, competitive).

    Parameters
    ----------
    num_players :
        Number of players (1-4).  When 1, behaves like the original
        single-player mode.
    hero_ids :
        Optional list of HeroId values, one per player.  If ``None``,
        players have no hero (vanilla stats).  Length must match
        ``num_players`` when provided.
    seed :
        Random seed for reproducible games.
    """

    MAX_PLAYERS = 4

    def __init__(
        self,
        num_players: int = 1,
        hero_ids: Optional[list[HeroId]] = None,
        seed: Optional[int] = None,
    ) -> None:
        if not 1 <= num_players <= self.MAX_PLAYERS:
            raise ValueError(f"num_players must be 1\\u2013{self.MAX_PLAYERS}")
        if hero_ids is not None and len(hero_ids) != num_players:
            raise ValueError("hero_ids length must match num_players")

        self.board: list[Tile] = generate_board(seed)
        self.is_night: bool = False
        self.turn_number: int = 0
        self.status: GameStatus = GameStatus.IN_PROGRESS
        self.winner: Optional[int] = None  # player_id of winner

        # --- Players ---
        self.players: list[Player] = []
        for i in range(num_players):
            p = Player(player_id=i, name=f"Player {i + 1}")
            if hero_ids is not None:
                hero = HEROES[hero_ids[i]]
                p.assign_hero(hero)
                p.name = hero.name
            self.players.append(p)

        # Turn rotation (fixed order: 0, 1, 2, ...)
        self._current_player_idx: int = 0

        # --- Shared finite content decks (one per level) ---
        self.monster_decks: dict[int, Deck[Monster]] = {
            1: Deck(list(C.MONSTER_POOL_L1), seed),
            2: Deck(list(C.MONSTER_POOL_L2), seed),
            3: Deck(list(C.MONSTER_POOL_L3), seed),
        }
        self.item_decks: dict[int, Deck[Item]] = {
            1: Deck(list(C.ITEM_POOL_L1), seed),
            2: Deck(list(C.ITEM_POOL_L2), seed),
            3: Deck(list(C.ITEM_POOL_L3), seed),
        }
        self.trait_deck: Deck[Trait] = Deck(list(C.TRAIT_POOL), seed)
        self.curse_deck: Deck[Curse] = Deck(list(C.CURSE_POOL), seed)

        # Each player gets their own movement deck
        self.movement_decks: dict[int, Deck[int]] = {
            i: Deck(list(C.MOVEMENT_DECK), seed, auto_reshuffle=True)
            for i in range(num_players)
        }

        # Simulated yes/no decision toggle for "you may" item prompts.
        # Even counter = Yes, odd counter = No (alternates each prompt).
        self._decision_counter: int = 0

    # ------------------------------------------------------------------
    # Convenience --- single-player backward compat
    # ------------------------------------------------------------------

    @property
    def player(self) -> Player:
        """Shortcut for single-player games (returns player 0)."""
        return self.players[0]

    @property
    def current_player(self) -> Player:
        """The player whose turn it is."""
        return self.players[self._current_player_idx]

    # ------------------------------------------------------------------
    # Decision helper (simulated for v0.1 — no real UI yet)
    # ------------------------------------------------------------------

    def _decide(self, prompt: str, log: list[str]) -> bool:
        """Simulated player decision: alternates Yes/No each time it is called.

        In v0.1 with no real UI, this stand-in lets us exercise both branches
        of every \'you may\' ability prompt during testing.
        """
        result = self._decision_counter % 2 == 0
        self._decision_counter += 1
        log.append(f"  [Decision] {prompt} \\u2192 {\'Yes\' if result else \'No\'}")
        return result

    # ------------------------------------------------------------------
    # Movement deck helpers
    # ------------------------------------------------------------------

    def draw_movement_cards(self, player: Player) -> None:
        """Draw cards until hand reaches effective_max_hand_size."""
        deck = self.movement_decks[player.player_id]
        while len(player.movement_hand) < player.effective_max_hand_size:
            card = deck.draw()
            if card is None:
                break
            player.movement_hand.append(card)

    # ------------------------------------------------------------------
    # Flee helper (Billfold: Fly, you dummy!)
    # ------------------------------------------------------------------

    def _apply_flee_move_back(self, player: Player, log: list[str]) -> None:
        """Move a player backward after fleeing (Billfold ability)."""
        if player.hero is None:
            return
        move_back = player.hero.flee_move_back
        old_pos = player.position
        new_pos = max(1, old_pos - move_back)
        player.position = new_pos
        log.append(
            f"  Fly, you dummy! {player.name} moves back {old_pos - new_pos} "
            f"spaces to tile {new_pos}."
        )

    # ------------------------------------------------------------------
    # Contagious Mutagen (Gregory)
    # ------------------------------------------------------------------

    def use_contagious_mutagen(
        self,
        source_player_id: int,
        target_player_id: int,
        curse_index: int = 0,
    ) -> list[str]:
        """Gregory\'s once-per-game ability: remove a curse and give it
        to another player.

        Returns log lines describing what happened.
        """
        log: list[str] = []
        source = self.players[source_player_id]
        target = self.players[target_player_id]

        if source.hero is None or not source.hero.has_contagious_mutagen:
            log.append("This player does not have the Contagious Mutagen ability.")
            return log
        if source.mutagen_used:
            log.append("Contagious Mutagen has already been used this game.")
            return log
        if source_player_id == target_player_id:
            log.append("Cannot target yourself with Contagious Mutagen.")
            return log
        if not source.curses:
            log.append("No curses to transfer.")
            return log

        idx = min(curse_index, len(source.curses) - 1)
        curse = source.curses.pop(idx)
        target.curses.append(curse)
        source.mutagen_used = True
        log.append(
            f"Contagious Mutagen: {source.name} transferred curse "
            f"\'{curse.name}\' to {target.name}!"
        )
        return log

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    def play_turn(
        self,
        card_index: int = 0,
        shop_choice: int = 0,
        flee: bool = False,
    ) -> TurnResult:
        """Execute one full turn for the current player.

        Parameters
        ----------
        card_index:
            Index into the player\'s movement_hand for the card to play.
        shop_choice:
            If landing on a Shop tile, the index of the item to pick.
        flee:
            If True and the player\'s hero supports fleeing, the player
            will flee instead of fighting (Billfold ability).

        Returns
        -------
        TurnResult with full log of what happened.
        """
        player = self.current_player

        if self.status != GameStatus.IN_PROGRESS:
            return TurnResult(
                turn_number=self.turn_number,
                player_id=player.player_id,
                card_played=0,
                moved_from=player.position,
                moved_to=player.position,
                tile_type_encountered=self.board[player.position].tile_type,
                encounter_log=["Game is already over."],
                game_status=self.status,
            )

        self.turn_number += 1
        log: list[str] = [f"[{player.name}\'s turn]"]

        # 1. Draw movement cards
        self.draw_movement_cards(player)

        if not player.movement_hand:
            log.append("No movement cards available \\u2014 turn skipped.")
            self._advance_turn()
            return TurnResult(
                turn_number=self.turn_number,
                player_id=player.player_id,
                card_played=0,
                moved_from=player.position,
                moved_to=player.position,
                tile_type_encountered=self.board[player.position].tile_type,
                encounter_log=log,
                game_status=self.status,
            )

        # 2. Movement phase
        # --- Wheelies: may reuse last played card value instead of playing new ---
        using_wheelies = False
        card_value: int
        if (
            player.last_card_played is not None
            and player.has_equipped_item("wheelies")
        ):
            if self._decide(
                f"Do you want to use Wheelies? (Last card played: {player.last_card_played})",
                log,
            ):
                using_wheelies = True
                card_value = player.last_card_played
                log.append(f"  Wheelies activated! Using last card value: {card_value}")

        if not using_wheelies:
            idx = min(card_index, len(player.movement_hand) - 1)
            card_value = player.movement_hand.pop(idx)
            # Track to discard pile and record as last played
            player.movement_discard.append(card_value)
            player.last_card_played = card_value

        # --- Hermes\' Shoes: treat 1 or 2 as 4 (optional) ---
        if card_value in (1, 2) and player.has_equipped_item("hermes_shoes"):
            if self._decide(
                f"Do you want to use Hermes\' Shoes? (Card value: {card_value} \\u2192 4)",
                log,
            ):
                card_value = 4
                log.append("  Hermes\' Shoes activated! Movement treated as 4.")

        # --- Boots of Agility: +1 to movement (optional) ---
        if player.has_equipped_item("boots_of_agility"):
            if self._decide(
                "Do you want to use Boots of Agility? (+1 to movement)",
                log,
            ):
                card_value += 1
                log.append(f"  Boots of Agility activated! Movement +1 \\u2192 {card_value}")

        modified_value = _fx.modify_movement_value(player, card_value, self.is_night)
        effective_move = modified_value + player.move_bonus
        effective_move = max(0, effective_move)

        old_pos = player.position
        new_pos = old_pos + effective_move

        # Truncate at miniboss if not defeated
        if not player.miniboss1_defeated and old_pos < 30 and new_pos >= 30:
            new_pos = 30
        if not player.miniboss2_defeated and old_pos < 60 and new_pos >= 60:
            new_pos = 60

        # Truncate at tile 90
        new_pos = min(new_pos, 90)

        player.position = new_pos
        log.append(
            f"Played card {card_value} (effective move {effective_move}): "
            f"tile {old_pos} \\u2192 tile {new_pos}"
        )

        # 3. Reveal tile
        tile = self.board[new_pos]
        if not tile.revealed:
            tile.revealed = True
            log.append(f"Tile {new_pos} revealed: {tile.tile_type.name}")
        else:
            log.append(f"Tile {new_pos} already revealed: {tile.tile_type.name}")

        # 4. Determine effective encounter (Night overrides)
        actual_type = tile.tile_type

        if self.is_night and actual_type not in (
            TileType.MINIBOSS,
            TileType.WERBLER,
            TileType.DAY_NIGHT,
        ):
            log.append("  Night override \\u2192 treated as Monster encounter.")
            actual_type = TileType.MONSTER

        # 5. Resolve encounter
        combat_result: Optional[CombatResult] = None
        level = get_level(new_pos)

        if actual_type == TileType.CHEST:
            enc.encounter_chest(player, self.item_decks[level], log, decide_fn=self._decide)

        elif actual_type == TileType.MONSTER:
            combat_result = enc.encounter_monster(
                player,
                self.monster_decks[level],
                self.trait_deck,
                self.curse_deck,
                log,
                is_night=self.is_night,
                flee=flee,
            )
            if flee and combat_result is None and player.hero and player.hero.can_flee_monsters:
                self._apply_flee_move_back(player, log)

        elif actual_type == TileType.SHOP:
            enc.encounter_shop(player, self.item_decks[level], log, shop_choice, decide_fn=self._decide)

        elif actual_type == TileType.BLANK:
            enc.encounter_blank(log)

        elif actual_type == TileType.DAY_NIGHT:
            self.is_night = enc.encounter_day_night(self.is_night, log)

        elif actual_type == TileType.MINIBOSS:
            already_defeated = (
                (new_pos == 30 and player.miniboss1_defeated)
                or (new_pos == 60 and player.miniboss2_defeated)
            )
            if already_defeated:
                log.append("Miniboss already defeated \\u2014 no encounter.")
            else:
                if new_pos == 30:
                    miniboss = C.MINIBOSS_1
                else:
                    miniboss = C.MINIBOSS_2
                combat_result = enc.encounter_miniboss(
                    player, miniboss, self.trait_deck, self.curse_deck, log,
                    is_night=self.is_night,
                    flee=flee,
                )
                if flee and combat_result is None and player.hero and player.hero.can_flee_miniboss:
                    self._apply_flee_move_back(player, log)
                elif combat_result == CombatResult.WIN:
                    if new_pos == 30:
                        player.miniboss1_defeated = True
                    else:
                        player.miniboss2_defeated = True

        elif actual_type == TileType.WERBLER:
            # Cannot flee the Werbler
            combat_result, self.status = enc.encounter_werbler(
                player, C.THE_WERBLER, self.trait_deck, self.curse_deck, log,
                is_night=self.is_night,
            )
            if self.status == GameStatus.WON:
                self.winner = player.player_id

        # Game-over message
        if self.status == GameStatus.WON:
            log.append(f"\\U0001f389 Game Over \\u2014 {player.name} Wins!")

        result = TurnResult(
            turn_number=self.turn_number,
            player_id=player.player_id,
            card_played=card_value if not using_wheelies else 0,
            moved_from=old_pos,
            moved_to=new_pos,
            tile_type_encountered=tile.tile_type,
            encounter_log=log,
            combat_result=combat_result,
            game_status=self.status,
        )

        # Advance to next player
        self._advance_turn()

        return result

    # ------------------------------------------------------------------
    # Turn rotation
    # ------------------------------------------------------------------

    def _advance_turn(self) -> None:
        """Move to the next player in rotation."""
        if len(self.players) > 1:
            self._current_player_idx = (
                (self._current_player_idx + 1) % len(self.players)
            )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def player_summary(self, player_id: int = 0) -> str:
        p = self.players[player_id]
        hero_name = p.hero.name if p.hero else "No hero"
        lines = [
            f"--- {p.name} ({hero_name}) ---",
            f"Position: tile {p.position} (Level {get_level(p.position)})",
            f"Strength: {p.total_strength}  (base {p.base_strength})",
            f"  Helmets:  {[i.name for i in p.helmets]}",
            f"  Chest:    {[i.name for i in p.chest_armor]}",
            f"  Legs:     {[i.name for i in p.leg_armor]}",
            f"  Weapons:  {[i.name for i in p.weapons]}",
            f"  Pack:     {[i.name for i in p.pack]}",
            f"Consumables: {[c.name for c in p.consumables]}",
            f"Traits:  {[t.name for t in p.traits]}",
            f"Curses:  {[c.name for c in p.curses]}",
            f"Hand:    {p.movement_hand}  Discard: {p.movement_discard}",
            f"Night:   {self.is_night}",
        ]
        return "\\n".join(lines)

    def all_players_summary(self) -> str:
        """Return a summary of all players."""
        return "\\n\\n".join(
            self.player_summary(p.player_id) for p in self.players
        )

    def visible_tiles(self) -> list[Tile]:
        """Return tiles currently visible.

        During Night (fog of war): only DayNight, Miniboss, and Werbler
        tiles are visible.  All other previously-revealed tiles are hidden.
        During Day: all revealed tiles are visible.
        """
        always_visible_types = (TileType.DAY_NIGHT, TileType.MINIBOSS, TileType.WERBLER)
        result: list[Tile] = []
        for tile in self.board[1:]:
            if tile.tile_type in always_visible_types:
                result.append(tile)
            elif not self.is_night and tile.revealed:
                result.append(tile)
        return result
'''

ENCOUNTERS_PY = '''"""Encounter resolution for each tile type --- RULES.md §7."""

from __future__ import annotations

from typing import Callable, Optional

from .types import (
    CombatResult,
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
        log.append(
            f"  Skimpy Armour: {destroyed.name} was shredded in defeat and discarded!"
        )


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
    want_equip = decide_fn(f"Equip {item.name} directly? (or add to pack)", log)

    if want_equip:
        if player.can_equip(item):
            player.equip(item)
            log.append(f"  {item.name} equipped.")
        else:
            # Slot full --- negotiate with currently equipped item
            slot_list = player._slot_list(item.slot)
            current = slot_list[-1]
            keep_in_pack = decide_fn(
                f"Slot full. Move {current.name} to pack to make room?", log
            )
            if keep_in_pack:
                if len(player.pack) < player.pack_size:
                    player.unequip(current)
                    player.pack.append(current)
                    player.equip(item)
                    log.append(f"  {current.name} moved to pack. {item.name} equipped.")
                else:
                    # Pack also full --- discard first pack item to make room
                    evicted = player.pack.pop(0)
                    log.append(f"  Pack full \\u2014 {evicted.name} discarded from pack.")
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
                log.append(f"  Cancelled \\u2014 {item.name} discarded.")
            else:
                evicted = player.pack.pop(0)
                player.pack.append(item)
                log.append(
                    f"  {evicted.name} discarded from pack. {item.name} added to pack."
                )


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
        log.append("Chest: item deck is empty \\u2014 nothing to draw.")
        return
    log.append(f"Chest: found {item.name} (+{item.strength_bonus} {item.slot.value})")
    if decide_fn is None:
        # Legacy / test path: auto-equip or discard
        if player.equip(item):
            log.append(f"  {item.name} equipped.")
        else:
            log.append(f"  No {item.slot.value} slot free \\u2014 {item.name} discarded.")
    else:
        _offer_item(player, item, log, decide_fn)


def encounter_monster(
    player: Player,
    monster_deck: Deck[Monster],
    trait_deck: Deck[Trait],
    curse_deck: Deck[Curse],
    log: list[str],
    is_night: bool = False,
    flee: bool = False,
) -> Optional[CombatResult]:
    """RULES §7.2 --- draw monster, resolve combat.

    If ``flee`` is True and the player\'s hero supports fleeing from
    monsters, the player escapes without penalty (no curse).
    The caller is responsible for moving the player back.
    """
    monster = monster_deck.draw()
    if monster is None:
        log.append("Monster: monster deck is empty \\u2014 no encounter.")
        return None

    # --- Flee check (Billfold: Fly, you dummy!) ---
    if flee and player.hero and player.hero.can_flee_monsters:
        log.append(
            f"Monster: {monster.name} (str {monster.strength}) appeared \\u2014 "
            f"{player.name} flees! No curse received."
        )
        return None  # no combat result

    log.append(f"Monster: fighting {monster.name} (str {monster.strength})")
    result = resolve_combat(player, monster, is_night=is_night)
    if result == CombatResult.WIN:
        trait = C.trait_for_monster(monster) if monster.trait_name else None
        if trait is None:
            trait = _pick_random_trait(trait_deck)
        if trait:
            player.traits.append(trait)
            log.append(f"  Victory! Gained trait: {trait.name}")
            _fx.on_trait_gained(player, trait, log)
        else:
            log.append("  Victory! (no traits left in deck)")
    elif result == CombatResult.LOSE:
        curse = C.curse_for_monster(monster) if monster.curse_name else None
        if curse is None:
            curse = _pick_random_curse(curse_deck)
        if curse:
            player.curses.append(curse)
            log.append(f"  Defeat! Gained curse: {curse.name}")
            _fx.on_curse_gained(player, curse, log)
        else:
            log.append("  Defeat! (no curses left in deck)")
        _apply_brunhilde_combat_loss(player, log)
    else:
        log.append("  Tie \\u2014 no trait or curse gained.")
    return result


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
    The number of items drawn depends on the player\'s hero
    (Billfold draws 4 instead of 3).
    """
    if not player.traits:
        log.append("Shop: no traits to trade \\u2014 shop cannot be used.")
        return

    draw_count = 3
    if player.hero:
        draw_count = player.hero.shop_draw_count

    items = item_deck.draw_many(draw_count)
    if not items:
        log.append("Shop: item deck is empty \\u2014 nothing to buy.")
        return

    idx = min(choose_index, len(items) - 1)
    chosen = items[idx]
    discarded_trait = player.traits.pop(0)  # discard oldest trait
    log.append(
        f"Shop: traded trait \'{discarded_trait.name}\' for {chosen.name}"
    )
    remaining_names = [it.name for it in items if it is not chosen]
    log.append(f"  Remaining items discarded: {remaining_names}")

    if decide_fn is None:
        # Legacy / test path: auto-equip or discard
        if player.equip(chosen):
            log.append(f"  {chosen.name} equipped.")
        else:
            log.append(f"  No {chosen.slot.value} slot free \\u2014 {chosen.name} discarded.")
    else:
        _offer_item(player, chosen, log, decide_fn)


def encounter_blank(log: list[str]) -> None:
    """RULES §7.4 --- no effect."""
    log.append("Blank tile \\u2014 nothing happens.")


def encounter_day_night(is_night: bool, log: list[str]) -> bool:
    """RULES §6 --- toggle day/night. Returns new is_night value."""
    new_state = not is_night
    if new_state:
        log.append("Day/Night tile \\u2014 night falls! Fog of war descends.")
    else:
        log.append("Day/Night tile \\u2014 dawn breaks! Fog lifts.")
    return new_state


def encounter_miniboss(
    player: Player,
    miniboss: Monster,
    trait_deck: Deck[Trait],
    curse_deck: Deck[Curse],
    log: list[str],
    is_night: bool = False,
    flee: bool = False,
) -> Optional[CombatResult]:
    """RULES §7.5 --- fight a miniboss. Must win to progress.

    If ``flee`` is True and the player\'s hero can flee minibosses,
    the player escapes without penalty.  The caller moves them back.
    """
    # --- Flee check (Billfold: Fly, you dummy!) ---
    if flee and player.hero and player.hero.can_flee_miniboss:
        log.append(
            f"Miniboss: {miniboss.name} (str {miniboss.strength}) \\u2014 "
            f"{player.name} flees! No curse received."
        )
        return None  # no combat, caller handles backward move

    log.append(f"Miniboss: fighting {miniboss.name} (str {miniboss.strength})")
    result = resolve_combat(player, miniboss, is_night=is_night)
    if result == CombatResult.WIN:
        trait = C.trait_for_monster(miniboss) if miniboss.trait_name else None
        if trait is None:
            trait = _pick_random_trait(trait_deck)
        if trait:
            player.traits.append(trait)
            log.append(f"  Victory! Gained trait: {trait.name}")
            _fx.on_trait_gained(player, trait, log)
        else:
            log.append("  Victory! (no traits left in deck)")
    elif result == CombatResult.LOSE:
        curse = C.curse_for_monster(miniboss) if miniboss.curse_name else None
        if curse is None:
            curse = _pick_random_curse(curse_deck)
        if curse:
            player.curses.append(curse)
            log.append(f"  Defeat! You remain on the miniboss tile.")
            _fx.on_curse_gained(player, curse, log)
        else:
            log.append("  Defeat! (no curses left in deck) \\u2014 remain on tile.")
    else:
        log.append("  Tie \\u2014 no progress, remain on tile.")
    return result


def encounter_werbler(
    player: Player,
    werbler: Monster,
    trait_deck: Deck[Trait],
    curse_deck: Deck[Curse],
    log: list[str],
    is_night: bool = False,
) -> tuple[CombatResult, GameStatus]:
    """RULES §7.6 --- final boss. Win -> game won; lose -> back to tile 61."""
    log.append(f"THE WERBLER: fighting {werbler.name} (str {werbler.strength})")
    result = resolve_combat(player, werbler, is_night=is_night)
    if result == CombatResult.WIN:
        log.append("  VICTORY! You defeated The Werbler!")
        return result, GameStatus.WON
    elif result == CombatResult.LOSE:
        curse = _pick_random_curse(curse_deck)
        if curse:
            player.curses.append(curse)
            _fx.on_curse_gained(player, curse, log)
        player.position = 61
        log.append("  Defeat! Sent back to tile 61 (start of Level 3).")
        return result, GameStatus.IN_PROGRESS
    else:
        log.append("  Tie \\u2014 no progress. Remain on tile 90.")
        return result, GameStatus.IN_PROGRESS
'''

base = pathlib.Path("werblers_engine")
(base / "game.py").write_text(GAME_PY, encoding="utf-8")
print("game.py written")
(base / "encounters.py").write_text(ENCOUNTERS_PY, encoding="utf-8")
print("encounters.py written")

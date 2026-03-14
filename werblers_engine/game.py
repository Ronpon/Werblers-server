"""Game orchestrator — ties board, player, decks, and encounters together.

Supports 1-4 players in competitive mode with fixed turn rotation.
"""

from __future__ import annotations

import random
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


def _item_to_dict(item: Item) -> dict:
    """Serialise an Item for the web UI."""
    return {
        "name":           item.name,
        "slot":           item.slot.value,
        "strength_bonus": item.strength_bonus,
        "effect_id":      item.effect_id,
        "hands":          item.hands,
        "tokens":         item.tokens,
        "is_consumable":  item.is_consumable,
    }


def _extract_gains(combat_info: dict, log: list, log_start: int, content_module) -> None:
    """Scan new log entries for trait/curse gains and add them to combat_info."""
    import re
    for entry in log[log_start:]:
        m = re.search(r"Victory! Gained trait[:\s]+(.+)", entry, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            combat_info["trait_gained"] = name
            combat_info["trait_gained_desc"] = content_module.TRAIT_DESCRIPTIONS.get(name, "")
        m = re.search(r"Gained curse[:\s]+(.+)", entry, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            combat_info["curse_gained"] = name
            combat_info["curse_gained_desc"] = content_module.CURSE_DESCRIPTIONS.get(name, "")


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
            raise ValueError(f"num_players must be 1\u2013{self.MAX_PLAYERS}")
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

        # --- Mini-boss decks (shuffled pools, one active per tier) ---
        self.miniboss_deck_t1: Deck[Monster] = Deck(list(C.MINIBOSS_POOL_T1), seed)
        self.miniboss_deck_t2: Deck[Monster] = Deck(list(C.MINIBOSS_POOL_T2), seed)
        self.active_miniboss_t1: Optional[Monster] = None
        self.active_miniboss_t2: Optional[Monster] = None

        # --- Werbler assignment (random, one per player, all different) ---
        rng = random.Random(seed)
        werbler_pool = list(C.WERBLER_POOL)
        rng.shuffle(werbler_pool)
        self.player_werblers: dict[int, Monster] = {}
        for i, p in enumerate(self.players):
            self.player_werblers[p.player_id] = werbler_pool[i]

        # Simulated yes/no decision toggle for "you may" item prompts.
        # Even counter = Yes, odd counter = No (alternates each prompt).
        self._decision_counter: int = 0

        # Pending offer state — set by begin_move(), consumed by resolve_offer()
        self._pending_offer: Optional[dict] = None

        # Last combat info — set by _resolve_auto_encounter for UI battle scene
        self._last_combat_info: Optional[dict] = None
        # Pending monster combat — set when a monster tile is hit (pre-fight pause)
        self._pending_combat: Optional[dict] = None
        # Extra STR bonus accumulated from consumables used in the pre-fight phase
        self._prefight_str_bonus: int = 0
        # Monster STR modifier accumulated from consumables used in the pre-fight phase
        self._prefight_monster_str_bonus: int = 0

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
        of every 'you may' ability prompt during testing.
        """
        result = self._decision_counter % 2 == 0
        self._decision_counter += 1
        log.append(f"  [Decision] {prompt} \u2192 {'Yes' if result else 'No'}")
        return result

    def _select(self, prompt: str, options: list[str], log: list[str]) -> int:
        """Simulated item selection: always picks the first option (index 0).

        In a real UI this would present a list and wait for the player to click
        a card.  The engine API accepts any callable with the same signature:
        ``(prompt: str, options: list[str], log: list[str]) -> int``
        """
        chosen = options[0] if options else "(none)"
        log.append(f"  [Select] {prompt} \u2192 {chosen}")
        return 0

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
    # Mage's Gauntlet — explicit turn action
    # ------------------------------------------------------------------

    def use_mages_gauntlet(self, player_id: int, trait_index: int = 0) -> list[str]:
        """Discard a trait to add a +1 Str token to an equipped Mage's Gauntlet.

        Can be called at any time during the current player's turn by a UI.
        Returns log lines describing what happened.
        """
        log: list[str] = []
        player = self.players[player_id]
        gauntlet = next(
            (w for w in player.weapons if w.effect_id == "mages_gauntlet"), None
        )
        if gauntlet is None:
            log.append("Mage's Gauntlet: not equipped.")
            return log
        if not player.traits:
            log.append("Mage's Gauntlet: no traits to discard.")
            return log
        idx = min(trait_index, len(player.traits) - 1)
        discarded_trait = player.traits.pop(idx)
        gauntlet.tokens += 1
        _fx.refresh_tokens(player)
        log.append(
            f"Mage's Gauntlet: discarded '{discarded_trait.name}', "
            f"added +1 Str token (gauntlet total: +{gauntlet.tokens} Str)."
        )
        return log

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
        """Gregory's once-per-game ability: remove a curse and give it
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
            f"'{curse.name}' to {target.name}!"
        )
        return log

    # ------------------------------------------------------------------
    # Me Too — PvP trigger when any player discards a curse
    # ------------------------------------------------------------------

    def _check_me_too(self, source_player: Player, log: list[str]) -> None:
        """When a player discards a curse, other players with Me Too may discard one."""
        for p in self.players:
            if p is source_player:
                continue
            me_too = next(
                (t for t in p.traits if t.effect_id == "me_too"), None
            )
            if me_too and p.curses:
                if self._decide(
                    f"Me Too!: {p.name}, discard a curse too?", log
                ):
                    removed = p.curses.pop(0)
                    _fx.refresh_tokens(p)
                    log.append(
                        f"  Me Too!: {p.name} discarded curse '{removed.name}'!"
                    )

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
            Index into the player's movement_hand for the card to play.
        shop_choice:
            If landing on a Shop tile, the index of the item to pick.
        flee:
            If True and the player's hero supports fleeing, the player
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
        log: list[str] = [f"[{player.name}'s turn]"]

        # 1. Draw movement cards
        self.draw_movement_cards(player)

        # --- Residuals: +1 Str every turn ---
        for trait in player.traits:
            if trait.effect_id == "residuals":
                trait.strength_bonus += 1
                log.append(
                    f"  Residuals: +1 Str token added (total: +{trait.strength_bonus})"
                )

        # --- Eight Lives: offer to discard trait to remove a T1/T2 curse ---
        eight_lives = next(
            (t for t in player.traits if t.effect_id == "eight_lives"), None
        )
        if eight_lives and player.curses and self._decide(
            "Eight Lives: Discard this trait to remove a Tier 1 or 2 curse?", log
        ):
            # Find a T1/T2 curse (source monsters level 1 or 2, or random curses)
            removable = [
                c for c in player.curses
                if not c.source_monster
                or any(
                    m.name == c.source_monster and m.level in (1, 2)
                    for pool in (C.MONSTER_POOL_L1, C.MONSTER_POOL_L2)
                    for m in pool
                )
            ]
            if removable:
                removed = removable[0]
                player.curses.remove(removed)
                player.traits.remove(eight_lives)
                _fx.refresh_tokens(player)
                log.append(f"  Eight Lives: discarded trait, removed curse '{removed.name}'!")
            else:
                log.append("  Eight Lives: no Tier 1/2 curses to remove.")

        # --- Meat's Back On the Menu: PvP — force opponent to discard minion ---
        meat_trait = next(
            (t for t in player.traits if t.effect_id == "meat_on_menu"), None
        )
        other_with_minions = [
            p for p in self.players
            if p is not player and p.minions
        ]
        if meat_trait and other_with_minions and self._decide(
            "Meat's Back On the Menu!: Force an opponent to discard a minion? (+5 Str tokens)", log
        ):
            target = other_with_minions[0]
            if target.minions:
                names = [m.name for m in target.minions]
                idx = self._select(
                    f"Meat's Back On the Menu!: Select one of {target.name}'s minions to discard:",
                    names,
                    log,
                )
                idx = max(0, min(idx, len(target.minions) - 1))
                lost_minion = target.minions.pop(idx)
                meat_trait.tokens += 5
                log.append(
                    f"  Meat's Back On the Menu!: {target.name} lost minion '{lost_minion.name}'. "
                    f"+5 Str tokens (total: +{meat_trait.tokens})."
                )

        # --- Mage's Gauntlet: offer once at start of turn (simulated) ---
        for gauntlet in list(player.weapons):
            if gauntlet.effect_id == "mages_gauntlet" and player.traits:
                if self._decide(
                    f"Mage's Gauntlet: Discard a trait for +1 Str token on {gauntlet.name}?",
                    log,
                ):
                    discarded_trait = player.traits.pop(0)
                    gauntlet.tokens += 1
                    _fx.refresh_tokens(player)
                    log.append(
                        f"  Mage's Gauntlet: discarded '{discarded_trait.name}', "
                        f"added +1 Str token (total: +{gauntlet.tokens} Str)."
                    )

        if not player.movement_hand:
            log.append("No movement cards available \u2014 turn skipped.")
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
        # --- Phase Shift: discard equip to toggle day/night ---
        if any(t.effect_id == "phase_shift" for t in player.traits):
            all_equips = (
                player.helmets + player.chest_armor
                + player.leg_armor + player.weapons
            )
            unlocked = [
                e for e in all_equips
                if not e.locked_by_curse_id
                or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
            ]
            if unlocked and self._decide(
                "Phase Shift: Discard an equip card to toggle day/night?", log
            ):
                discarded = unlocked[0]
                player.unequip(discarded)
                self.is_night = not self.is_night
                _fx.refresh_tokens(player)
                state = "Night" if self.is_night else "Day"
                log.append(f"  Phase Shift: discarded {discarded.name}. Time changed to {state}!")

        # --- Touchdown: may discard trait to teleport to Werbler tile ---
        td_trait = next(
            (t for t in player.traits if t.effect_id == "touchdown"), None
        )
        if td_trait and self._decide(
            "Touchdown!: Discard this trait to teleport to the Werbler tile (tile 90)?", log
        ):
            player.traits.remove(td_trait)
            _fx.refresh_tokens(player)
            player.position = 90
            log.append("  Touchdown!: teleported to tile 90 (Werbler)!")
            # Skip normal movement and go directly to encounter
            tile = self.board[90]
            tile.revealed = True
            log.append(f"Tile 90: {tile.tile_type.name}")
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned — skipping.")
            else:
                combat_result, self.status = enc.encounter_werbler(
                    player, werbler, self.curse_deck, log,
                    is_night=self.is_night,
                    decide_fn=self._decide,
                    select_fn=self._select,
                    other_players=[p for p in self.players if p is not player],
                    monster_deck_l3=self.monster_decks[3],
                )
            if self.status == GameStatus.WON:
                self.winner = player.player_id
                log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
            self._advance_turn()
            return TurnResult(
                turn_number=self.turn_number,
                player_id=player.player_id,
                card_played=0,
                moved_from=player.position,
                moved_to=90,
                tile_type_encountered=TileType.WERBLER,
                encounter_log=log,
                combat_result=combat_result,
                game_status=self.status,
            )

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
            # Bad Trip curse: movement hand is kept facedown, card played randomly
            if any(c.effect_id == "bad_trip" for c in player.curses):
                idx = random.randrange(len(player.movement_hand))
                log.append("  Bad Trip: cards facedown \u2014 randomly selecting!")
            else:
                idx = min(card_index, len(player.movement_hand) - 1)
            card_value = player.movement_hand.pop(idx)
            # Track to discard pile and record as last played
            player.movement_discard.append(card_value)
            player.last_card_played = card_value

        # --- So Lethargic: -1 Str token when playing a 3 or 4 ---
        if card_value in (3, 4):
            for lethargic_curse in player.curses:
                if lethargic_curse.effect_id == "so_lethargic":
                    lethargic_curse.strength_bonus -= 1
                    log.append(
                        f"  So\u2026 Lethargic\u2026: played a {card_value}, "
                        f"-1 Str token added (now {lethargic_curse.strength_bonus})"
                    )

        # --- Hermes' Shoes: treat 1 or 2 as 4 (optional) ---
        if card_value in (1, 2) and player.has_equipped_item("hermes_shoes"):
            if self._decide(
                f"Do you want to use Hermes' Shoes? (Card value: {card_value} \u2192 4)",
                log,
            ):
                card_value = 4
                log.append("  Hermes' Shoes activated! Movement treated as 4.")

        # --- Boots of Agility: +1 to movement (optional) ---
        if player.has_equipped_item("boots_of_agility"):
            if self._decide(
                "Do you want to use Boots of Agility? (+1 to movement)",
                log,
            ):
                card_value += 1
                log.append(f"  Boots of Agility activated! Movement +1 \u2192 {card_value}")

        # --- Fancy Footwork: optionally reduce movement by 1 or 2 ---
        if any(t.effect_id == "fancy_footwork" for t in player.traits):
            if self._decide("Fancy Footwork: Reduce your movement this turn?", log):
                reduce_two = self._decide(
                    "Fancy Footwork: Reduce by 2? (No = reduce by 1)", log
                )
                reduction = 2 if reduce_two else 1
                card_value = max(0, card_value - reduction)
                log.append(f"  Fancy Footwork: movement reduced by {reduction} \u2192 {card_value}")

        modified_value = _fx.modify_movement_value(player, card_value, self.is_night)
        effective_move = modified_value + player.move_bonus
        effective_move = max(0, effective_move)

        old_pos = player.position
        new_pos = old_pos + effective_move

        # Truncate at miniboss if not defeated.
        # Uses new_pos > 30/60 (not old_pos < 30/60) so that a player who
        # remains ON the miniboss tile after a loss cannot slip past it on
        # their next turn without winning the fight.
        if not player.miniboss1_defeated and new_pos > 30:
            new_pos = 30
        if not player.miniboss2_defeated and new_pos > 60:
            new_pos = 60

        # Truncate at tile 90
        new_pos = min(new_pos, 90)

        player.position = new_pos
        log.append(
            f"Played card {card_value} (effective move {effective_move}): "
            f"tile {old_pos} \u2192 tile {new_pos}"
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
            log.append("  Night override \u2192 treated as Monster encounter.")
            actual_type = TileType.MONSTER

        # 5. Resolve encounter
        combat_result: Optional[CombatResult] = None
        level = get_level(new_pos)

        if actual_type == TileType.CHEST:
            enc.encounter_chest(player, self.item_decks[level], log, decide_fn=self._decide)

        elif actual_type == TileType.MONSTER:
            other_players = [p for p in self.players if p is not player]
            # --- No More Charlie Work: may draw from next tier ---
            effective_monster_deck = self.monster_decks[level]
            if level < 3 and any(
                t.effect_id == "no_more_charlie_work" for t in player.traits
            ):
                if self._decide(
                    f"No More Charlie Work: Fight from Tier {level + 1} instead of Tier {level}?",
                    log,
                ):
                    effective_monster_deck = self.monster_decks[level + 1]
                    log.append(f"  No More Charlie Work: drawing from Tier {level + 1}!")

            combat_result = enc.encounter_monster(
                player,
                effective_monster_deck,
                self.trait_deck,
                self.curse_deck,
                log,
                is_night=self.is_night,
                flee=flee,
                decide_fn=self._decide,
                select_fn=self._select,
                other_players=other_players,
                all_players=self.players,
                monster_decks=self.monster_decks,
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
                log.append("Miniboss already defeated \u2014 no encounter.")
            else:
                # Determine which tier and get/reveal the active miniboss
                if new_pos == 30:
                    if self.active_miniboss_t1 is None:
                        self.active_miniboss_t1 = self.miniboss_deck_t1.draw()
                    miniboss = self.active_miniboss_t1
                    reward_deck = self.item_decks[2]  # T1 boss → T2 reward
                else:
                    if self.active_miniboss_t2 is None:
                        self.active_miniboss_t2 = self.miniboss_deck_t2.draw()
                    miniboss = self.active_miniboss_t2
                    reward_deck = self.item_decks[3]  # T2 boss → T3 reward

                if miniboss is None:
                    # All bosses for this tier defeated; player passes freely
                    log.append("All minibosses for this tier have been defeated!")
                    if new_pos == 30:
                        player.miniboss1_defeated = True
                    else:
                        player.miniboss2_defeated = True
                else:
                    combat_result = enc.encounter_miniboss(
                        player, miniboss, reward_deck, log,
                        is_night=self.is_night,
                        flee=flee,
                        decide_fn=self._decide,
                        select_fn=self._select,
                        other_players=[p for p in self.players if p is not player],
                    )
                    if flee and combat_result is None and player.hero and player.hero.can_flee_miniboss:
                        self._apply_flee_move_back(player, log)
                    elif combat_result == CombatResult.WIN:
                        if new_pos == 30:
                            player.miniboss1_defeated = True
                            self.active_miniboss_t1 = None  # defeated → next visitor reveals new one
                        else:
                            player.miniboss2_defeated = True
                            self.active_miniboss_t2 = None

        elif actual_type == TileType.WERBLER:
            # Cannot flee the Werbler
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned — skipping.")
            else:
                combat_result, self.status = enc.encounter_werbler(
                    player, werbler, self.curse_deck, log,
                    is_night=self.is_night,
                    decide_fn=self._decide,
                    select_fn=self._select,
                    other_players=[p for p in self.players if p is not player],
                    monster_deck_l3=self.monster_decks[3],
                )
                if self.status == GameStatus.WON:
                    self.winner = player.player_id

        # --- Pending movement draws (Quite the Setback, My Hands are Awesome, etc.) ---
        while player._pending_movement_draws > 0:
            card = self.movement_decks[player.player_id].draw()
            if card is not None:
                player.movement_hand.append(card)
                log.append(f"  Drew movement card {card} (pending draw).")
            player._pending_movement_draws -= 1

        # --- Me Too: when an opponent loses a curse, player with Me Too may discard one ---
        if len(self.players) > 1:
            for other in self.players:
                if other is player:
                    continue
                me_too = next(
                    (t for t in other.traits if t.effect_id == "me_too"), None
                )
                if me_too and other.curses:
                    # "When another player discards a curse, discard one of yours too"
                    # For now, trigger once per turn if the active player lost any curse
                    # (covers combat-loss curse removal via It's Not Your Fault, Kamikaze Gun, etc.)
                    if self._decide(
                        f"Me Too!: {other.name}, discard one of your curses? "
                        f"(triggered by {player.name}'s turn)", log
                    ):
                        removed = other.curses.pop(0)
                        _fx.refresh_tokens(other)
                        log.append(f"  Me Too!: {other.name} discarded curse '{removed.name}'.")

        # Game-over message
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")

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
    # Interactive turn API  (Phase 1 + Phase 2)
    # ------------------------------------------------------------------

    def get_available_abilities(self) -> list[dict]:
        """Return "you may" abilities the current player can activate this turn.

        Returns a list of dicts describing each ability and any extra inputs
        the UI needs to collect (trait select, equip select, etc.).
        """
        player = self.current_player
        # Ensure the hand is populated before checking wheelies / hand size
        self.draw_movement_cards(player)
        abilities: list[dict] = []

        for trait in player.traits:
            eid = trait.effect_id
            if eid == "eight_lives" and player.curses:
                abilities.append({
                    "id": "eight_lives",
                    "label": "Eight Lives",
                    "description": "Discard this trait to remove one of your Tier 1 or 2 curses.",
                    "type": "toggle",
                })
            elif eid == "meat_on_menu":
                targets = [p for p in self.players if p is not player and p.minions]
                if targets:
                    abilities.append({
                        "id": "meat_on_menu",
                        "label": "Meat's Back on the Menu!",
                        "description": "Force an opponent to discard a minion. Gain +5 Str tokens.",
                        "type": "select_player_minion",
                        "targets": [
                            {"player_id": t.player_id, "name": t.name,
                             "minions": [m.name for m in t.minions]}
                            for t in targets
                        ],
                    })
            elif eid == "touchdown":
                abilities.append({
                    "id": "touchdown",
                    "label": "Touchdown!",
                    "description": "Discard this trait to teleport directly to tile 90 (The Werbler).",
                    "type": "toggle",
                })
            elif eid == "fancy_footwork":
                abilities.append({
                    "id": "fancy_footwork",
                    "label": "Fancy Footwork",
                    "description": "Reduce your movement this turn by 1 or 2.",
                    "type": "select_number",
                    "options": [1, 2],
                })
            elif eid == "phase_shift":
                all_equips = (
                    player.helmets + player.chest_armor
                    + player.leg_armor + player.weapons
                )
                unlocked = [
                    e for e in all_equips
                    if not e.locked_by_curse_id
                    or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
                ]
                if unlocked:
                    abilities.append({
                        "id": "phase_shift",
                        "label": "Phase Shift",
                        "description": "Discard an equip card to toggle the Day/Night cycle.",
                        "type": "select_equip",
                        "equips": [e.name for e in unlocked],
                    })

        for item in player.weapons:
            if item.effect_id == "mages_gauntlet" and player.traits:
                abilities.append({
                    "id": "mages_gauntlet",
                    "label": "Mage's Gauntlet",
                    "description": "Discard a trait to add a permanent +1 Str token to your Gauntlet.",
                    "type": "select_trait",
                    "traits": [t.name for t in player.traits],
                })

        # Wheelies — replaces card play entirely
        if player.has_equipped_item("wheelies") and player.last_card_played is not None:
            abilities.append({
                "id": "wheelies",
                "label": "Wheelies",
                "description": (
                    f"Reuse your last played card value ({player.last_card_played}) "
                    "instead of playing a new card."
                ),
                "type": "toggle",
            })

        # Post-card passive abilities (applied automatically after card is chosen)
        if player.has_equipped_item("hermes_shoes"):
            abilities.append({
                "id": "hermes_shoes",
                "label": "Hermes' Shoes",
                "description": "If you play a 1 or 2, treat it as 4 instead.",
                "type": "toggle",
                "timing": "post_card",
            })
        if player.has_equipped_item("boots_of_agility"):
            abilities.append({
                "id": "boots_of_agility",
                "label": "Boots of Agility",
                "description": "+1 to your movement this turn.",
                "type": "toggle",
                "timing": "post_card",
            })

        return abilities

    def begin_move(
        self,
        card_index: int = 0,
        flee: bool = False,
        activated: Optional[dict] = None,
        direction: str = "forward",
    ) -> dict:
        """Phase-1 of an interactive turn.

        Handles pre-turn abilities, card play, movement, and tile reveal.
        For CHEST / SHOP tiles the drawn item(s) are stored in
        ``self._pending_offer`` and the method returns early with
        ``phase == "offer_chest"`` or ``"offer_shop"``so the UI can ask the
        player what to do with them.  All other tile types are resolved
        automatically and return ``phase == "done"``.

        Parameters
        ----------
        card_index:
            Index of the movement card to play from the current player's hand.
        flee:
            Whether the player is fleeing (Billfold ability).
        activated:
            Dict of ability IDs → args. Supported keys:
            ``eight_lives`` (bool), ``meat_on_menu`` (dict with
            ``target_player_id`` and ``minion_index``),
            ``mages_gauntlet`` (dict with ``trait_index``),
            ``phase_shift`` (dict with ``equip_index``),
            ``touchdown`` (bool), ``wheelies`` (bool),
            ``hermes_shoes`` (bool), ``boots_of_agility`` (bool),
            ``fancy_footwork`` (dict with ``reduction``).
        """
        if activated is None:
            activated = {}

        player = self.current_player
        self.turn_number += 1
        log: list[str] = [f"[{player.name}'s turn]"]

        # 1. Draw movement cards
        self.draw_movement_cards(player)

        # 2. Residuals — automatic
        for trait in player.traits:
            if trait.effect_id == "residuals":
                trait.strength_bonus += 1
                log.append(f"  Residuals: +1 Str token (total: +{trait.strength_bonus})")

        # 3. Eight Lives
        if activated.get("eight_lives"):
            eight_lives = next(
                (t for t in player.traits if t.effect_id == "eight_lives"), None
            )
            removable = [
                c for c in player.curses
                if not c.source_monster
                or any(
                    m.name == c.source_monster and m.level in (1, 2)
                    for pool in (C.MONSTER_POOL_L1, C.MONSTER_POOL_L2)
                    for m in pool
                )
            ]
            if eight_lives and removable:
                removed = removable[0]
                player.curses.remove(removed)
                player.traits.remove(eight_lives)
                _fx.refresh_tokens(player)
                log.append(
                    f"  Eight Lives: discarded trait, removed curse '{removed.name}'!"
                )

        # 4. Meat's Back on Menu
        meat_args = activated.get("meat_on_menu")
        if meat_args:
            meat_trait = next(
                (t for t in player.traits if t.effect_id == "meat_on_menu"), None
            )
            if meat_trait:
                target_id = int(meat_args.get("target_player_id", -1))
                minion_idx = int(meat_args.get("minion_index", 0))
                target = next(
                    (p for p in self.players if p.player_id == target_id), None
                )
                if target and target.minions:
                    idx = min(minion_idx, len(target.minions) - 1)
                    lost = target.minions.pop(idx)
                    meat_trait.tokens += 5
                    log.append(
                        f"  Meat's Back on Menu!: {target.name} lost '{lost.name}'. "
                        f"+5 Str tokens on trait."
                    )

        # 5. Mage's Gauntlet
        gauntlet_args = activated.get("mages_gauntlet")
        if gauntlet_args:
            gauntlet = next(
                (w for w in player.weapons if w.effect_id == "mages_gauntlet"), None
            )
            if gauntlet and player.traits:
                tidx = min(int(gauntlet_args.get("trait_index", 0)), len(player.traits) - 1)
                discarded = player.traits.pop(tidx)
                gauntlet.tokens += 1
                _fx.refresh_tokens(player)
                log.append(
                    f"  Mage's Gauntlet: discarded '{discarded.name}', "
                    f"+1 Str token (total: +{gauntlet.tokens})."
                )

        # 6. Phase Shift
        phase_args = activated.get("phase_shift")
        if phase_args and any(t.effect_id == "phase_shift" for t in player.traits):
            all_equips = (
                player.helmets + player.chest_armor
                + player.leg_armor + player.weapons
            )
            unlocked = [
                e for e in all_equips
                if not e.locked_by_curse_id
                or not any(c.effect_id == e.locked_by_curse_id for c in player.curses)
            ]
            eidx = min(int(phase_args.get("equip_index", 0)), len(unlocked) - 1)
            if unlocked:
                to_discard = unlocked[eidx]
                player.unequip(to_discard)
                self.is_night = not self.is_night
                _fx.refresh_tokens(player)
                log.append(
                    f"  Phase Shift: discarded {to_discard.name}. "
                    f"{'Night' if self.is_night else 'Day'}!"
                )

        # 7. Touchdown (early exit)
        if activated.get("touchdown"):
            td = next((t for t in player.traits if t.effect_id == "touchdown"), None)
            if td:
                player.traits.remove(td)
                _fx.refresh_tokens(player)
                old_pos = player.position
                player.position = 90
                log.append("  Touchdown!: teleported to tile 90 (Werbler)!")
                tile = self.board[90]
                tile.revealed = True
                werbler = self.player_werblers.get(player.player_id)
                if werbler is None:
                    log.append("No werbler assigned — skipping.")
                    combat_result = None
                else:
                    combat_result, self.status = enc.encounter_werbler(
                        player, werbler, self.curse_deck, log,
                        is_night=self.is_night,
                        decide_fn=self._decide,
                        select_fn=self._select,
                        other_players=[p for p in self.players if p is not player],
                        monster_deck_l3=self.monster_decks[3],
                    )
                if self.status == GameStatus.WON:
                    self.winner = player.player_id
                    log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": 90,
                    "card_played": 0, "tile_type": TileType.WERBLER.name,
                    "combat_result": combat_result.name if combat_result else None,
                    "game_status": self.status.name, "winner": self.winner,
                }

        # 8. Empty hand check
        if not player.movement_hand:
            log.append("No movement cards — turn skipped.")
            self._finish_post_encounter(player, log)
            self._advance_turn()
            return {
                "phase": "done", "log": log,
                "moved_from": player.position, "moved_to": player.position,
                "card_played": 0, "tile_type": self.board[player.position].tile_type.name,
                "combat_result": None, "game_status": self.status.name, "winner": self.winner,
            }

        # 9. Wheelies or normal card play
        using_wheelies = False
        card_value: int
        if (
            activated.get("wheelies")
            and player.last_card_played is not None
            and player.has_equipped_item("wheelies")
        ):
            using_wheelies = True
            card_value = player.last_card_played
            log.append(f"  Wheelies! Using last card value: {card_value}")
        else:
            if any(c.effect_id == "bad_trip" for c in player.curses):
                idx = random.randrange(len(player.movement_hand))
                log.append("  Bad Trip: cards facedown — randomly selecting!")
            else:
                idx = min(card_index, len(player.movement_hand) - 1)
            card_value = player.movement_hand.pop(idx)
            player.movement_discard.append(card_value)
            player.last_card_played = card_value

        # So Lethargic
        if card_value in (3, 4):
            for c in player.curses:
                if c.effect_id == "so_lethargic":
                    c.strength_bonus -= 1
                    log.append(
                        f"  So\u2026 Lethargic\u2026: played {card_value}, "
                        f"-1 Str token ({c.strength_bonus})"
                    )

        # 10. Post-card movement modifiers
        if (
            activated.get("hermes_shoes")
            and card_value in (1, 2)
            and player.has_equipped_item("hermes_shoes")
        ):
            card_value = 4
            log.append("  Hermes' Shoes! Movement treated as 4.")

        if (
            activated.get("boots_of_agility")
            and player.has_equipped_item("boots_of_agility")
        ):
            card_value += 1
            log.append(f"  Boots of Agility! Movement +1 \u2192 {card_value}")

        ff_args = activated.get("fancy_footwork")
        if ff_args and any(t.effect_id == "fancy_footwork" for t in player.traits):
            reduction = int(ff_args.get("reduction", 1))
            card_value = max(0, card_value - reduction)
            log.append(f"  Fancy Footwork: reduced by {reduction} \u2192 {card_value}")

        # 11. Movement calculation
        modified_value = _fx.modify_movement_value(player, card_value, self.is_night)
        effective_move = max(0, modified_value + player.move_bonus)

        old_pos = player.position
        if direction == "backward":
            new_pos = max(1, old_pos - effective_move)
        else:
            new_pos = old_pos + effective_move

        # Miniboss gates — use new_pos > threshold (not old_pos < threshold)
        # so a player already stuck ON the miniboss tile after a loss cannot slip past.
        if not player.miniboss1_defeated and new_pos > 30:
            new_pos = 30
        if not player.miniboss2_defeated and new_pos > 60:
            new_pos = 60
        new_pos = min(new_pos, 90)

        player.position = new_pos
        log.append(
            f"Played card {card_value} (effective {effective_move}): "
            f"tile {old_pos} \u2192 {new_pos}"
        )

        # 12. Reveal tile
        tile = self.board[new_pos]
        if self.is_night:
            if not tile.revealed_night:
                tile.revealed_night = True
                log.append(f"Tile {new_pos} visited at night (still hidden during day)")
            else:
                log.append(f"Tile {new_pos}: {tile.tile_type.name} (night, already night-visited)")
        else:
            if not tile.revealed:
                tile.revealed = True
                log.append(f"Tile {new_pos} revealed: {tile.tile_type.name}")
            else:
                log.append(f"Tile {new_pos}: {tile.tile_type.name}")

        # 13. Determine effective encounter type (night override)
        actual_type = tile.tile_type
        if self.is_night and actual_type not in (
            TileType.MINIBOSS, TileType.WERBLER, TileType.DAY_NIGHT,
        ):
            log.append("  Night override \u2192 Monster encounter.")
            actual_type = TileType.MONSTER

        level = get_level(new_pos)

        # 14. Chest — pause for interactive offer
        if actual_type == TileType.CHEST:
            item = self.item_decks[level].draw()
            if item is None:
                log.append("Chest: item deck is empty \u2014 nothing to draw.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            log.append(f"Chest: found {item.name} (STR +{item.strength_bonus}, {item.slot.value})")
            self._pending_offer = {
                "type": "chest", "level": level, "items": [item],
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
            }
            return {
                "phase": "offer_chest", "log": log,
                "moved_from": old_pos, "moved_to": new_pos, "card_played": card_value,
                "tile_type": tile.tile_type.name,
                "offer": {"items": [_item_to_dict(item)]},
            }

        # 15. Shop — pause for interactive offer
        if actual_type == TileType.SHOP:
            draw_count = 3
            items = self.item_decks[level].draw_many(draw_count)
            if not items:
                log.append("Shop: item deck is empty \u2014 nothing to buy.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            log.append(f"Shop: choose from {[i.name for i in items]}")
            self._pending_offer = {
                "type": "shop", "level": level, "items": items,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
            }
            return {
                "phase": "offer_shop", "log": log,
                "moved_from": old_pos, "moved_to": new_pos, "card_played": card_value,
                "tile_type": tile.tile_type.name,
                "offer": {
                    "items": [_item_to_dict(i) for i in items],
                },
            }

        # 15.5 MONSTER — pause for pre-fight consumable phase
        if actual_type == TileType.MONSTER:
            self._prefight_str_bonus = 0
            other_players = [p for p in self.players if p is not player]

            # Check for No More Charlie Work — pause for player decision
            if level < 3 and any(t.effect_id == "no_more_charlie_work" for t in player.traits):
                self._pending_combat = {
                    "type": "awaiting_charlie_work",
                    "level": level,
                    "other_players": other_players,
                    "log": log,
                    "old_pos": old_pos, "new_pos": new_pos,
                    "card_value": card_value, "tile_type": tile.tile_type.name,
                }
                return {
                    "phase": "charlie_work",
                    "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "level": level,
                }

            effective_monster_deck = self.monster_decks[level]
            monster = effective_monster_deck.draw()
            if monster is None:
                log.append("Monster: monster deck is empty \u2014 no encounter.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            has_reroll = any(
                t.effect_id in ("ill_come_in_again", "i_see_everything")
                for t in player.traits
            )
            self._pending_combat = {
                "monster": monster,
                "effective_deck": effective_monster_deck,
                "other_players": other_players,
                "level": level,
                "log": log,
                "old_pos": old_pos,
                "new_pos": new_pos,
                "card_value": card_value,
                "tile_type": tile.tile_type.name,
                "ill_come_in_again_available": has_reroll,
            }
            combat_info = {
                "monster_name": monster.name,
                "monster_strength": monster.strength,
                "player_strength": player.combat_strength(),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "monster",
                "level": level,
                "result": None,
                "ill_come_in_again_available": has_reroll,
            }
            self._last_combat_info = combat_info
            return {
                "phase": "combat",
                "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "combat_info": combat_info,
            }

        # 15.6 MINIBOSS — pause for pre-fight phase (like MONSTER)
        if actual_type == TileType.MINIBOSS:
            already_defeated = (
                (new_pos == 30 and player.miniboss1_defeated)
                or (new_pos == 60 and player.miniboss2_defeated)
            )
            if already_defeated:
                log.append("Miniboss already defeated \u2014 no encounter.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            if new_pos == 30:
                if self.active_miniboss_t1 is None:
                    self.active_miniboss_t1 = self.miniboss_deck_t1.draw()
                miniboss = self.active_miniboss_t1
                reward_deck_level = 2
            else:
                if self.active_miniboss_t2 is None:
                    self.active_miniboss_t2 = self.miniboss_deck_t2.draw()
                miniboss = self.active_miniboss_t2
                reward_deck_level = 3
            if miniboss is None:
                log.append("All minibosses for this tier have been defeated!")
                if new_pos == 30:
                    player.miniboss1_defeated = True
                else:
                    player.miniboss2_defeated = True
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            self._prefight_str_bonus = 0
            self._prefight_monster_str_bonus = 0
            self._pending_combat = {
                "type": "miniboss",
                "monster": miniboss,
                "reward_deck_level": reward_deck_level,
                "boss_tile": new_pos,
                "other_players": [p for p in self.players if p is not player],
                "level": 1 if new_pos == 30 else 2,
                "log": log,
                "old_pos": old_pos, "new_pos": new_pos,
                "card_value": card_value, "tile_type": tile.tile_type.name,
            }
            # Compute ability modifiers for pre-fight STR display
            _ab_log: list[str] = []
            _ab_player_mod, _ab_monster_mod, _ = enc._apply_miniboss_modifiers(
                player, miniboss, _ab_log, self.is_night)
            self._pending_combat["ability_player_mod"] = _ab_player_mod
            self._pending_combat["ability_monster_mod"] = _ab_monster_mod
            self._pending_combat["ability_breakdown"] = _ab_log
            combat_info = {
                "monster_name": miniboss.name,
                "monster_strength": miniboss.strength + _ab_monster_mod,
                "player_strength": player.combat_strength() + _ab_player_mod,
                "ability_player_mod": _ab_player_mod,
                "ability_monster_mod": _ab_monster_mod,
                "ability_breakdown": _ab_log,
                "description": miniboss.description,
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "miniboss",
                "level": 1 if new_pos == 30 else 2,
                "result": None,
            }
            self._last_combat_info = combat_info
            return {
                "phase": "combat", "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "combat_info": combat_info,
            }

        # 15.7 WERBLER — pause for pre-fight phase
        if actual_type == TileType.WERBLER:
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned \u2014 skipping.")
                self._finish_post_encounter(player, log)
                self._advance_turn()
                return {
                    "phase": "done", "log": log,
                    "moved_from": old_pos, "moved_to": new_pos,
                    "card_played": card_value, "tile_type": tile.tile_type.name,
                    "combat_result": None, "game_status": self.status.name, "winner": self.winner,
                }
            self._prefight_str_bonus = 0
            self._prefight_monster_str_bonus = 0
            self._pending_combat = {
                "type": "werbler",
                "monster": werbler,
                "other_players": [p for p in self.players if p is not player],
                "level": 3,
                "log": log,
                "old_pos": old_pos, "new_pos": new_pos,
                "card_value": card_value, "tile_type": tile.tile_type.name,
            }
            combat_info = {
                "monster_name": werbler.name,
                "monster_strength": werbler.strength,
                "player_strength": player.combat_strength(),
                "description": werbler.description,
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "werbler",
                "level": 3,
                "result": None,
            }
            self._last_combat_info = combat_info
            return {
                "phase": "combat", "log": log,
                "moved_from": old_pos, "moved_to": new_pos,
                "card_played": card_value, "tile_type": tile.tile_type.name,
                "combat_info": combat_info,
            }

        # 16. All other tile types — auto-resolve
        combat_result = self._resolve_auto_encounter(
            player, actual_type, tile, level, flee, log
        )
        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": old_pos, "moved_to": new_pos,
            "card_played": card_value, "tile_type": tile.tile_type.name,
            "combat_result": combat_result.name if combat_result else None,
            "combat_info": self._last_combat_info,
            "game_status": self.status.name, "winner": self.winner,
        }

    def use_ill_come_in_again(self) -> dict:
        """Use I'll Come In Again / I See Everything: return current monster and draw a new one."""
        pc = self._pending_combat
        if pc is None or not pc.get("ill_come_in_again_available"):
            return {"error": "Trait not available for this encounter"}
        monster = pc["monster"]
        deck = pc["effective_deck"]
        deck.put_bottom(monster)
        new_monster = deck.draw()
        if new_monster is None:
            # Deck was empty after returning — restore original and abort
            deck.put_bottom(monster)
            return {"error": "Monster deck is empty — cannot draw a replacement"}
        pc["monster"] = new_monster
        pc["ill_come_in_again_available"] = False  # one use per encounter
        player = self.current_player
        log = pc.get("log", [])
        log.append(f"  I'll Come In Again!: sent {monster.name} back, drew {new_monster.name}.")
        combat_info = {
            "monster_name": new_monster.name,
            "monster_strength": new_monster.strength,
            "player_strength": player.combat_strength(),
            "player_id": player.player_id,
            "player_name": player.name,
            "hero_id": player.hero.id.name if player.hero else None,
            "category": "monster",
            "level": pc.get("level", 1),
            "result": None,
            "ill_come_in_again_available": False,
        }
        self._last_combat_info = combat_info
        return {"phase": "combat", "combat_info": combat_info}

    def fight(self) -> dict:
        """Resolve the pending combat (monster, miniboss, or werbler) after the pre-fight phase."""
        if self._pending_combat is None:
            return {"error": "No pending combat", "phase": "error"}

        player = self.current_player  # turn has not advanced yet
        pc = self._pending_combat
        self._pending_combat = None

        combat_type = pc.get("type", "monster")
        log = pc["log"]
        old_pos = pc["old_pos"]
        new_pos = pc["new_pos"]
        card_value = pc["card_value"]
        tile_type_name = pc["tile_type"]
        level = pc["level"]
        log_start = len(log)

        extra_str = self._prefight_str_bonus
        self._prefight_str_bonus = 0
        monster_str_delta = self._prefight_monster_str_bonus
        self._prefight_monster_str_bonus = 0
        combat_result = None

        # Capture player strength BEFORE combat so displayed value isn't
        # inflated or reduced by traits/curses gained during resolution.
        def _no_consumable_decide(prompt: str, log_: list) -> bool:
            """In interactive fights, consumables are pre-used via the UI.
            Refuse all consumable-phase auto-decisions to prevent double use."""
            if "consumable" in prompt.lower() or "play a" in prompt.lower():
                return False
            return self._decide(prompt, log_)

        if combat_type == "miniboss":
            miniboss = pc["monster"]
            reward_deck_level = pc["reward_deck_level"]
            boss_tile = pc["boss_tile"]
            other_players = pc["other_players"]
            player_str_at_fight = player.combat_strength() + pc.get("ability_player_mod", 0)
            combat_result = enc.encounter_miniboss(
                player, miniboss, self.item_decks[reward_deck_level], log,
                is_night=self.is_night, flee=False,
                decide_fn=_no_consumable_decide, select_fn=self._select,
                other_players=other_players,
            )
            if combat_result == CombatResult.WIN:
                if boss_tile == 30:
                    player.miniboss1_defeated = True
                    self.active_miniboss_t1 = None
                else:
                    player.miniboss2_defeated = True
                    self.active_miniboss_t2 = None
            self._last_combat_info = {
                "monster_name": miniboss.name,
                "monster_strength": miniboss.strength + pc.get("ability_monster_mod", 0),
                "player_strength": player_str_at_fight,
                "ability_player_mod": pc.get("ability_player_mod", 0),
                "ability_monster_mod": pc.get("ability_monster_mod", 0),
                "ability_breakdown": pc.get("ability_breakdown", []),
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "miniboss",
                "level": level,
                "result": combat_result.name if combat_result else None,
            }

        elif combat_type == "werbler":
            werbler = pc["monster"]
            other_players = pc["other_players"]
            player_str_at_fight = player.combat_strength()
            combat_result, self.status = enc.encounter_werbler(
                player, werbler, self.curse_deck, log,
                is_night=self.is_night,
                decide_fn=_no_consumable_decide, select_fn=self._select,
                other_players=other_players,
                monster_deck_l3=self.monster_decks[3],
            )
            if self.status == GameStatus.WON:
                self.winner = player.player_id
            self._last_combat_info = {
                "monster_name": werbler.name,
                "monster_strength": werbler.strength,
                "player_strength": player_str_at_fight,
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "werbler",
                "level": level,
                "result": combat_result.name if combat_result else None,
            }

        else:  # monster
            monster = pc["monster"]
            if monster_str_delta:
                monster.strength = max(0, monster.strength + monster_str_delta)
            effective_deck = pc["effective_deck"]
            other_players = pc["other_players"]
            player_str_at_fight = player.combat_strength() + extra_str
            combat_result = enc.encounter_monster(
                player,
                effective_deck,
                self.trait_deck,
                self.curse_deck,
                log,
                is_night=self.is_night,
                flee=False,
                decide_fn=_no_consumable_decide,
                select_fn=self._select,
                other_players=other_players,
                all_players=self.players,
                monster_decks=self.monster_decks,
                pre_drawn_monster=monster,
                extra_player_strength=extra_str,
            )
            self._last_combat_info = {
                "monster_name": monster.name,
                "monster_strength": monster.strength,
                "player_strength": player_str_at_fight,
                "player_id": player.player_id,
                "player_name": player.name,
                "hero_id": player.hero.id.name if player.hero else None,
                "category": "monster",
                "level": level,
                "result": combat_result.name if combat_result else None,
            }

        # Extract trait/curse gained from new log entries
        _extract_gains(self._last_combat_info, log, log_start, C)

        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": old_pos, "moved_to": new_pos,
            "card_played": card_value, "tile_type": tile_type_name,
            "combat_result": combat_result.name if combat_result else None,
            "combat_info": self._last_combat_info,
            "game_status": self.status.name, "winner": self.winner,
        }

    def resolve_charlie_work(self, use_it: bool) -> dict:
        """Resolve the No More Charlie Work decision.

        Call after begin_move returned phase == "charlie_work".
        use_it=True → draw monster from the next tier; False → draw from current tier.
        """
        pending = self._pending_combat
        self._pending_combat = None
        if pending is None or pending.get("type") != "awaiting_charlie_work":
            return {"phase": "done", "log": ["No pending Charlie Work decision."],
                    "game_status": self.status.name, "winner": self.winner}

        player = self.current_player
        level: int = pending["level"]
        other_players: list = pending["other_players"]
        log: list[str] = pending["log"]

        if use_it:
            effective_monster_deck = self.monster_decks[level + 1]
            log.append(f"  No More Charlie Work: drawing from Tier {level + 1}!")
        else:
            effective_monster_deck = self.monster_decks[level]

        monster = effective_monster_deck.draw()
        if monster is None:
            log.append("Monster: monster deck is empty — no encounter.")
            self._finish_post_encounter(player, log)
            self._advance_turn()
            return {
                "phase": "done", "log": log,
                "moved_from": pending["old_pos"], "moved_to": pending["new_pos"],
                "card_played": pending["card_value"], "tile_type": pending["tile_type"],
                "combat_result": None, "game_status": self.status.name, "winner": self.winner,
            }

        self._pending_combat = {
            "monster": monster,
            "effective_deck": effective_monster_deck,
            "other_players": other_players,
            "level": level,
            "log": log,
            "old_pos": pending["old_pos"],
            "new_pos": pending["new_pos"],
            "card_value": pending["card_value"],
            "tile_type": pending["tile_type"],
        }
        combat_info = {
            "monster_name": monster.name,
            "monster_strength": monster.strength,
            "player_strength": player.combat_strength(),
            "player_id": player.player_id,
            "player_name": player.name,
            "hero_id": player.hero.id.name if player.hero else None,
            "category": "monster",
            "level": level,
            "result": None,
        }
        self._last_combat_info = combat_info
        return {
            "phase": "combat",
            "log": log,
            "moved_from": pending["old_pos"], "moved_to": pending["new_pos"],
            "card_played": pending["card_value"], "tile_type": pending["tile_type"],
            "combat_info": combat_info,
        }

    def resolve_offer(self, choices: Optional[dict] = None) -> dict:
        """Phase-2 of an interactive turn: apply item placement choices.

        Must be called after ``begin_move`` returned ``phase == "offer_chest"``
        or ``"offer_shop"``.

        choices (chest)::
            {
              "take":               bool,           # True = take item
              "placement":          "equip"|"pack",
              "equip_action":       "swap"|"discard",  # if slot was full
              "equip_item_index":   int,            # which item in the slot to swap/discard
              "pack_discard_index": int,            # which pack slot to evict (if pack full)
              "adaptable_blade_two_handed": bool,
            }
        choices (shop)::
            {
              "chosen_index":       int,   # which of the offered items to keep
              "trait_index":        int,   # which trait to trade away (default 0)
              plus same placement keys as chest
            }
        """
        if choices is None:
            choices = {}

        pending = self._pending_offer
        self._pending_offer = None

        if pending is None:
            return {"phase": "done", "log": ["No pending offer."],
                    "game_status": self.status.name, "winner": self.winner}

        player = self.current_player
        offer_type = pending["type"]
        log: list[str] = []

        if offer_type == "chest":
            item = pending["items"][0]
            if choices.get("take", False):
                self._apply_item_to_player(player, item, choices, log)
            else:
                log.append(f"  {item.name} left behind.")

        elif offer_type == "shop":
            if not choices.get("take", True):
                log.append("Shop: left without taking.")
            else:
                items: list[Item] = pending["items"]
                cidx = min(int(choices.get("chosen_index", 0)), len(items) - 1)
                chosen = items[cidx]
                log.append(f"Shop: took {chosen.name}.")
                remaining = [i.name for i in items if i is not chosen]
                if remaining:
                    log.append(f"  Remaining items discarded: {remaining}")
                self._apply_item_to_player(player, chosen, choices, log)

        self._finish_post_encounter(player, log)
        if self.status == GameStatus.WON:
            log.append(f"\U0001f389 Game Over \u2014 {player.name} Wins!")
        self._advance_turn()
        return {
            "phase": "done", "log": log,
            "moved_from": pending["moved_from"], "moved_to": pending["moved_to"],
            "card_played": pending["card_played"], "tile_type": pending["tile_type"],
            "combat_result": None, "game_status": self.status.name, "winner": self.winner,
        }

    def _apply_item_to_player(
        self,
        player: Player,
        item: Item,
        choices: dict,
        log: list[str],
    ) -> None:
        """Apply item placement choices (mirrors _offer_item but choice-driven)."""
        # Consumable wrapper — add directly to consumables list
        if item.is_consumable:
            import copy as _copy
            consumable = next((c for c in C.CONSUMABLE_POOL if c.name == item.name), None)
            if consumable:
                player.consumables.append(_copy.copy(consumable))
                log.append(f"  {item.name} added to consumables.")
            else:
                log.append(f"  {item.name} (consumable) — unknown type, discarded.")
            return

        # Adaptable Blade configuration
        if item.effect_id == "adaptable_blade":
            if choices.get("adaptable_blade_two_handed"):
                item.hands = 2
                item.strength_bonus = 8
                log.append("  Adaptable Blade: configured as 2H (+8 Str).")
            else:
                item.hands = 1
                item.strength_bonus = 4
                log.append("  Adaptable Blade: configured as 1H (+4 Str).")

        placement = choices.get("placement", "pack")

        if placement == "equip":
            if player.can_equip(item):
                player.equip(item)
                log.append(f"  {item.name} equipped.")
            else:
                slot_list = player._slot_list(item.slot)
                if not slot_list:
                    # No valid slot at all — treat as pack
                    if player.add_to_pack(item):
                        log.append(f"  Cannot equip {item.name} — added to pack.")
                    else:
                        log.append(f"  Cannot equip {item.name} and pack full — discarded.")
                else:
                    cur_idx = min(
                        int(choices.get("equip_item_index", len(slot_list) - 1)),
                        len(slot_list) - 1,
                    )
                    current = slot_list[cur_idx]
                    action = choices.get("equip_action", "swap")
                    if action == "swap":
                        if player.pack_slots_free > 0:
                            player.unequip(current)
                            player.pack.append(current)
                            player.equip(item)
                            log.append(
                                f"  {current.name} moved to pack. {item.name} equipped."
                            )
                        else:
                            pack_idx = min(
                                int(choices.get("pack_discard_index", 0)),
                                len(player.pack) - 1,
                            )
                            evicted = player.pack.pop(pack_idx)
                            log.append(f"  Pack full \u2014 {evicted.name} discarded.")
                            player.unequip(current)
                            player.pack.append(current)
                            player.equip(item)
                            log.append(
                                f"  {current.name} moved to pack. {item.name} equipped."
                            )
                    else:  # discard currently equipped
                        player.unequip(current)
                        player.equip(item)
                        log.append(f"  {current.name} discarded. {item.name} equipped.")
        else:  # pack
            if player.add_to_pack(item):
                log.append(f"  {item.name} added to pack.")
            else:
                pack_idx = min(
                    int(choices.get("pack_discard_index", 0)),
                    len(player.pack) - 1,
                )
                evicted = player.pack.pop(pack_idx)
                player.pack.append(item)
                log.append(f"  {evicted.name} discarded from pack. {item.name} added.")

        _fx.refresh_tokens(player)

    def _resolve_auto_encounter(
        self,
        player: Player,
        actual_type: TileType,
        tile,
        level: int,
        flee: bool,
        log: list[str],
    ) -> Optional[CombatResult]:
        """Auto-resolve all non-chest/shop encounters (used by begin_move)."""
        import re as _re
        combat_result: Optional[CombatResult] = None
        new_pos = tile.index
        self._last_combat_info = None
        log_before = len(log)

        if actual_type == TileType.BLANK:
            enc.encounter_blank(log)

        elif actual_type == TileType.DAY_NIGHT:
            self.is_night = enc.encounter_day_night(self.is_night, log)

        elif actual_type == TileType.MONSTER:
            other_players = [p for p in self.players if p is not player]
            effective_deck = self.monster_decks[level]
            if level < 3 and any(
                t.effect_id == "no_more_charlie_work" for t in player.traits
            ):
                if self._decide(
                    f"No More Charlie Work: Fight from Tier {level + 1}?", log
                ):
                    effective_deck = self.monster_decks[level + 1]
                    log.append(f"  No More Charlie Work: drawing from Tier {level + 1}!")
            combat_result = enc.encounter_monster(
                player, effective_deck, self.trait_deck, self.curse_deck, log,
                is_night=self.is_night, flee=flee,
                decide_fn=self._decide, select_fn=self._select,
                other_players=other_players, all_players=self.players,
                monster_decks=self.monster_decks,
            )
            if flee and combat_result is None and player.hero and player.hero.can_flee_monsters:
                self._apply_flee_move_back(player, log)

        elif actual_type == TileType.MINIBOSS:
            already_defeated = (
                (new_pos == 30 and player.miniboss1_defeated)
                or (new_pos == 60 and player.miniboss2_defeated)
            )
            if already_defeated:
                log.append("Miniboss already defeated \u2014 no encounter.")
            else:
                if new_pos == 30:
                    if self.active_miniboss_t1 is None:
                        self.active_miniboss_t1 = self.miniboss_deck_t1.draw()
                    miniboss = self.active_miniboss_t1
                    reward_deck = self.item_decks[2]
                else:
                    if self.active_miniboss_t2 is None:
                        self.active_miniboss_t2 = self.miniboss_deck_t2.draw()
                    miniboss = self.active_miniboss_t2
                    reward_deck = self.item_decks[3]

                if miniboss is None:
                    log.append("All minibosses for this tier have been defeated!")
                    if new_pos == 30:
                        player.miniboss1_defeated = True
                    else:
                        player.miniboss2_defeated = True
                else:
                    combat_result = enc.encounter_miniboss(
                        player, miniboss, reward_deck, log,
                        is_night=self.is_night, flee=flee,
                        decide_fn=self._decide, select_fn=self._select,
                        other_players=[p for p in self.players if p is not player],
                    )
                    if flee and combat_result is None and player.hero and player.hero.can_flee_miniboss:
                        self._apply_flee_move_back(player, log)
                    elif combat_result == CombatResult.WIN:
                        if new_pos == 30:
                            player.miniboss1_defeated = True
                            self.active_miniboss_t1 = None
                        else:
                            player.miniboss2_defeated = True
                            self.active_miniboss_t2 = None

        elif actual_type == TileType.WERBLER:
            werbler = self.player_werblers.get(player.player_id)
            if werbler is None:
                log.append("No werbler assigned — skipping.")
            else:
                combat_result, self.status = enc.encounter_werbler(
                    player, werbler, self.curse_deck, log,
                    is_night=self.is_night,
                    decide_fn=self._decide, select_fn=self._select,
                    other_players=[p for p in self.players if p is not player],
                    monster_deck_l3=self.monster_decks[3],
                )
                if self.status == GameStatus.WON:
                    self.winner = player.player_id

        # Extract combat info from log for UI battle scene
        if combat_result is not None or (actual_type in (TileType.MONSTER, TileType.MINIBOSS, TileType.WERBLER)):
            monster_name = None
            monster_str = None
            category = "monster"
            for line in log[log_before:]:
                m = _re.search(r'(?:Monster|Miniboss|THE WERBLER): fighting (.+?) \(str (\d+)\)', line)
                if m:
                    monster_name = m.group(1)
                    monster_str = int(m.group(2))
                if 'Miniboss:' in line:
                    category = "miniboss"
                if 'THE WERBLER:' in line:
                    category = "werbler"
            if monster_name:
                self._last_combat_info = {
                    "monster_name": monster_name,
                    "monster_strength": monster_str,
                    "player_strength": player.combat_strength(),
                    "player_id": player.player_id,
                    "player_name": player.name,
                    "hero_id": player.hero.id.name if player.hero else None,
                    "category": category,
                    "level": level,
                    "result": combat_result.name if combat_result else None,
                }

        return combat_result

    def _finish_post_encounter(self, player: Player, log: list[str]) -> None:
        """Handle post-encounter housekeeping: pending draws and Me Too."""
        while player._pending_movement_draws > 0:
            card = self.movement_decks[player.player_id].draw()
            if card is not None:
                player.movement_hand.append(card)
                log.append(f"  Drew movement card {card} (pending draw).")
            player._pending_movement_draws -= 1

        if len(self.players) > 1:
            for other in self.players:
                if other is player:
                    continue
                me_too = next(
                    (t for t in other.traits if t.effect_id == "me_too"), None
                )
                if me_too and other.curses:
                    if self._decide(
                        f"Me Too!: {other.name}, discard a curse?", log
                    ):
                        removed = other.curses.pop(0)
                        _fx.refresh_tokens(other)
                        log.append(
                            f"  Me Too!: {other.name} discarded curse '{removed.name}'."
                        )

    # ------------------------------------------------------------------
    # Turn rotation
    # ------------------------------------------------------------------

    def _advance_turn(self) -> None:
        """Move to the next player in rotation and prefill their hand."""
        if len(self.players) > 1:
            self._current_player_idx = (
                (self._current_player_idx + 1) % len(self.players)
            )
        # Prefill current player's hand so they see a full hand when it's their turn
        self.draw_movement_cards(self.current_player)

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
        return "\n".join(lines)

    def all_players_summary(self) -> str:
        """Return a summary of all players."""
        return "\n\n".join(
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

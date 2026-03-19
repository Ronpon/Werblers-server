"""Quick test: Wheel monster prize path + server-side combat setup simulation."""
import random
from werblers_engine import mystery as mys, content as C
from werblers_engine.deck import Deck
from werblers_engine.player import Player
from werblers_engine.heroes import HEROES, HeroId

p = Player(player_id=0, name='Test')
p._hero = HEROES[HeroId.BILLFOLD]

item_decks = {1: Deck(list(C.ITEM_POOL_L1), seed=1), 2: Deck(list(C.ITEM_POOL_L2), seed=1), 3: Deck(list(C.ITEM_POOL_L3), seed=1)}
monster_decks = {1: Deck(list(C.MONSTER_POOL_L1), seed=1), 2: Deck(list(C.MONSTER_POOL_L2), seed=1), 3: Deck(list(C.MONSTER_POOL_L3), seed=1)}
trait_deck = Deck(list(C.TRAIT_POOL), seed=1)

monster_count = 0
for seed in range(500):
    rng = random.Random(seed)
    log = []
    try:
        result = mys.resolve_the_wheel(
            p, 1, item_decks, monster_decks, trait_deck, log, rng
        )
        if result.get('prize_type') == 'monster':
            m = result['monster']
            monster_count += 1
            # Simulate what app.py does when prize_type == 'monster'
            _male_bonus = 0
            if hasattr(m, 'bonus_vs_male') and m.bonus_vs_male and p.hero and p.hero.is_male:
                _male_bonus = m.bonus_vs_male
            combat_info = {
                "monster_name": m.name,
                "monster_strength": m.strength + _male_bonus,
                "player_strength": p.combat_strength(),
                "player_id": p.player_id,
                "player_name": p.name,
                "hero_id": p.hero.id.name if p.hero else None,
                "category": "monster",
                "level": result.get("tier", 1),
                "result": None,
            }
            # Simulate _enrich_combat_info fields
            card_image = f"Monsters/Finished Cards/{m.name} Card.png"
            bg_map = {1: "Backgrounds/Forest Background.png", 2: "Backgrounds/Cave Background.png", 3: "Backgrounds/Dungeon Background.png"}
            background = bg_map.get(combat_info["level"], bg_map[1])
            print(f"Seed {seed}: MONSTER - {m.name} (str={m.strength}, lvl={m.level}, tier_result={result.get('tier',1)})")
            print(f"  combat_info OK: hero_id={combat_info['hero_id']}, bg={background}, card={card_image}")
    except Exception as e:
        import traceback
        print(f"Seed {seed}: ERROR - {e}")
        traceback.print_exc()

print(f"\nDone. Found {monster_count} monster results out of 500 spins.")

"""Test mystery box server endpoint for 500 errors."""
import sys
sys.path.insert(0, 'web_ui')

import app as flask_app
import werblers_engine.mystery as _mys
from werblers_engine.types import Item, EquipSlot

client = flask_app.app.test_client()

errors = 0
prize_seen = set()

for trial in range(200):
    # Start a fresh game each time for clean state
    r = client.post('/api/new_game', json={'num_players': 1, 'hero_ids': ['BRUNHILDE']})
    if r.status_code != 200:
        print(f"Trial {trial}: new_game failed {r.status_code}")
        errors += 1
        continue

    game = flask_app._game
    player = game.current_player

    # Give player items to wager
    for i in range(3):
        player.pack.append(Item(name=f'Sword {i}', slot=EquipSlot.WEAPON, strength_bonus=i+1))

    tier = (trial % 3) + 1
    event = _mys.MysteryEvent(
        event_id='mystery_box', name='Mystery Box', tier=tier,
        description='test', image_name='Mystery Box'
    )
    game._pending_offer = {
        'type': 'mystery',
        'event': event,
        'level': 1,
        'log': [],
        'moved_from': 1, 'moved_to': 2,
        'card_played': 3, 'tile_type': 'mystery',
    }

    r = client.post('/api/resolve_mystery', json={'action': 'open', 'wager_index': 0})
    if r.status_code != 200:
        data = r.get_json() or {}
        print(f"Trial {trial} (tier {tier}): HTTP {r.status_code} - {data.get('error', 'unknown')}")
        errors += 1
    else:
        data = r.get_json()
        pt = data.get('prize_type', '?')
        ph = data.get('phase', '?')
        prize_seen.add(f"{pt}/{ph}")

print(f"\nPrize types seen: {sorted(prize_seen)}")
print(f"Total errors: {errors}")
if errors == 0:
    print("ALL PASSED")
else:
    print(f"FAILED: {errors} errors")

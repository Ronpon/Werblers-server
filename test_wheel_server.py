"""Test the Wheel endpoint end-to-end via Flask test client."""
import sys
sys.path.insert(0, '.')

from web_ui.app import app
import web_ui.app as _app_module
from werblers_engine import mystery as mys

client = app.test_client()

# Start new game
r = client.post('/api/new_game', json={'num_players': 1, 'seed': 42})
print(f"new_game: {r.status_code} ok={r.get_json().get('ok')}")

# Reload _game reference after it's been set by the route
game = _app_module._game
player = game.players[0]
print(f"player pos: {player.position}")

# Roll a wheel event
import random
rng = random.Random(1)
event = mys.roll_mystery_event(player.position)
while event.event_id != 'the_wheel':
    event = mys.roll_mystery_event(player.position, rng)
print(f"event: {event.event_id} tier={event.tier}")

# Inject pending offer
game._pending_offer = {
    'type': 'mystery',
    'event': event,
    'level': 1,
    'moved_from': player.position,
    'moved_to': player.position,
    'card_played': 1,
    'tile_type': 'MYSTERY',
    'log': [],
}

# Run many spins covering different prize_types by using different seeds
import random as _rand

prize_types_seen = set()
errors = []

for seed in range(500):
    # Re-inject fresh offer each time
    import random as _r2
    rng_spin = _r2.Random(seed)
    game._pending_offer = {
        'type': 'mystery',
        'event': event,
        'level': 1,
        'moved_from': 1,
        'moved_to': 1,
        'card_played': 1,
        'tile_type': 'MYSTERY',
        'log': [],
    }
    # Also reset pending_combat to avoid conflicts
    game._pending_combat = None

    r2 = client.post('/api/resolve_mystery', json={'action': 'spin'})
    data = r2.get_json() or {}
    prize_type = data.get('prize_type', '?')
    phase = data.get('phase', '?')

    if r2.status_code != 200:
        errors.append(f"Seed {seed}: HTTP {r2.status_code} prize={prize_type} phase={phase} err={data.get('error','')}")
    else:
        key = f"{prize_type}/{phase}"
        if key not in prize_types_seen:
            prize_types_seen.add(key)
            print(f"Seed {seed}: NEW prize_type={prize_type} phase={phase}")

print(f"\nTotal errors: {len(errors)}")
for e in errors[:10]:
    print(f"  {e}")
print(f"Prize types seen: {sorted(prize_types_seen)}")

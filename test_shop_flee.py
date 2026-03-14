import sys, json
sys.path.insert(0, 'web_ui')
import app as wapp

client = wapp.app.test_client()
resp = client.post('/api/new_game',
    data=json.dumps({'num_players': 1, 'hero_ids': ['BILLFOLD'], 'seed': 42}),
    content_type='application/json')

g = wapp._game
p = g.player
print('hero:', p.hero.name, 'shop_draw_count:', p.hero.shop_draw_count)

from werblers_engine.types import TileType
hero_bonus = p.hero.movement_card_bonus
# Find a shop tile
shop_tile = next(t for t in g.board[1:30] if t.tile_type == TileType.SHOP)
card_val = 1
effective_move = card_val + hero_bonus
start_pos = shop_tile.index - effective_move
print(f'shop_tile index={shop_tile.index}, start_pos={start_pos}')
p.position = max(1, start_pos)
p.movement_hand = [card_val]

resp = client.post('/api/begin_move',
    data=json.dumps({'card_index': 0, 'flee': False, 'activated': {}, 'direction': 'forward'}),
    content_type='application/json')
data = json.loads(resp.data)
print('begin_move phase:', data.get('phase'))
if data.get('phase') == 'offer_shop':
    items = data['offer']['items']
    print(f'Number of items shown: {len(items)}')
    for it in items:
        print(f'  - {it["name"]} ({it["slot"]})')
else:
    print('actual tile:', data.get('tile_type'))

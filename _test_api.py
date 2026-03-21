import urllib.request, json
resp = urllib.request.urlopen('http://127.0.0.1:5001/api/heroes')
d = json.loads(resp.read())
print('Type:', type(d).__name__, '| Count:', len(d))
h = d[0]
print('First hero id:', h['id'])
print('name:', h['name'])
print('card_image:', h['card_image'])
print('has animations:', 'animations' in h)

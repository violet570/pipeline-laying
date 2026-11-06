import json, os, collections
RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')

def load(name):
    with open(os.path.join(RAW, name + '.json'), encoding='utf-8') as f:
        return json.load(f)

b = load('buildings')
roads = load('roads')
areas = load('areas')
pois = load('pois')
bound = load('campus_boundary')

def center(el):
    g = el.get('geometry') or []
    g = [p for p in g if p]
    return (sum(p['lat'] for p in g) / len(g), sum(p['lon'] for p in g) / len(g)) if g else (None, None)

print('=== buildings:', len(b['elements']))
rows = []
for el in b['elements']:
    t = el.get('tags', {})
    lat, lon = center(el)
    rows.append((t.get('name', '(unnamed)'), t.get('building', '?'), t.get('building:levels', ''), round(lat, 5), round(lon, 5), len(el.get('geometry') or [])))
rows.sort()
for r in rows:
    print(' | '.join(map(str, r)))

print('\n=== roads:', len(roads['elements']))
print(collections.Counter(el['tags'].get('highway') for el in roads['elements']))
print('=== areas:', len(areas['elements']))
print(collections.Counter((el['tags'].get('landuse') or el['tags'].get('leisure') or el['tags'].get('natural') or el['tags'].get('amenity') or '?') for el in areas['elements']))
print('=== pois:', len(pois['elements']))
for el in pois['elements']:
    t = el.get('tags', {})
    nm = t.get('name') or ''
    if nm or t.get('amenity') in ('parking', 'bicycle_parking'):
        print(' ', el['id'], nm, t.get('amenity') or t.get('shop') or t.get('barrier') or t.get('power') or '', round(el['lat'], 5), round(el['lon'], 5))
print('=== boundary:')
for el in bound['elements']:
    print(' ', el['id'], el['tags'].get('name'), len(el.get('geometry') or []))

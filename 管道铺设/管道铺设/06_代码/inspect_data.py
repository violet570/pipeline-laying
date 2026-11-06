import json, os
RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'derived')
os.makedirs(OUT, exist_ok=True)

def load(name):
    with open(os.path.join(RAW, name + '.json'), encoding='utf-8') as f:
        return json.load(f)

lines = []
lines.append('=== POIS ===')
for el in load('pois')['elements']:
    t = el.get('tags', {})
    lines.append(f"{el['id']} | {t.get('name','')} | {json.dumps(t, ensure_ascii=False)} | {el['lat']:.6f},{el['lon']:.6f}")

lines.append('\n=== BUILDINGS ===')
b = load('buildings')['elements']
for el in b:
    t = el.get('tags', {})
    g = [p for p in (el.get('geometry') or []) if p]
    lat = sum(p['lat'] for p in g)/len(g)
    lon = sum(p['lon'] for p in g)/len(g)
    lines.append(f"{el['id']} | {t.get('name','')} | {json.dumps(t, ensure_ascii=False)} | {lat:.6f},{lon:.6f} | n={len(g)}")

lines.append('\n=== AREAS ===')
for el in load('areas')['elements']:
    t = el.get('tags', {})
    g = [p for p in (el.get('geometry') or []) if p]
    if not g:
        continue
    lat = sum(p['lat'] for p in g)/len(g)
    lon = sum(p['lon'] for p in g)/len(g)
    lines.append(f"{el['id']} | {t.get('name','')} | {json.dumps(t, ensure_ascii=False)} | {lat:.6f},{lon:.6f}")

with open(os.path.join(OUT, 'inspect.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('wrote', os.path.join(OUT, 'inspect.txt'), len(lines), 'lines')

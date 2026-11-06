"""Join the traced plaza spurs to the MAIN OSM road component only.

An earlier version snapped to "the nearest OSM vertex", which in this area can
be a stray `path` vertex that belongs to its own little island — the traced ring
then ended up in a disconnected component and the MST could not reach the three
colleges. This version first splits the OSM road graph into connected
components, keeps only the largest one (the real campus network), and snaps the
spurs to vertices of THAT component.

usage: python scripts/connect_plaza_ring.py
"""
import collections
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))


def xy(lon, lat):
    return (lon - LON0) * K_LON, (lat - LAT0) * K_LAT


def _same(p, q, eps=1e-9):
    return abs(p[0] - q[0]) < eps and abs(p[1] - q[1]) < eps


def main():
    els = json.load(open('data/raw/roads_with_plaza.json', encoding='utf-8'))['elements']
    roads = [e for e in els
             if (e.get('tags') or {}).get('source') != 'user_trace'
             and (e.get('tags') or {}).get('highway') not in (None, 'steps', 'construction')]

    # --- build the OSM road graph, exact-node matching ----------------------
    reg, adj, coords = {}, collections.defaultdict(list), {}

    def node(lon, lat):
        k = (round(lon, 7), round(lat, 7))
        if k not in reg:
            reg[k] = len(reg)
            coords[reg[k]] = (lon, lat)
        return reg[k]

    for el in roads:
        g = [p for p in (el.get('geometry') or []) if p]
        ids = [node(p['lon'], p['lat']) for p in g]
        for i in range(len(ids) - 1):
            a, b = ids[i], ids[i + 1]
            if a != b:
                adj[a].append(b)
                adj[b].append(a)

    # --- largest connected component ---------------------------------------
    comp = {}
    cid = 0
    for s in adj:
        if s in comp:
            continue
        q, comp[s] = [s], cid
        while q:
            u = q.pop()
            for v in adj[u]:
                if v not in comp:
                    comp[v] = cid
                    q.append(v)
        cid += 1
    sizes = collections.Counter(comp.values())
    main_c = max(sizes, key=sizes.get)
    ranked = sorted(sizes.values(), reverse=True)[:5]
    print(f'osm nodes {len(reg)}, components {len(sizes)}, sizes {ranked}')
    print(f'keeping main component {main_c} with {sizes[main_c]} nodes')

    main_nodes = [(coords[n][0], coords[n][1]) for n in adj if comp[n] == main_c]

    # --- snap each spur's outer end onto that component ---------------------
    # Iterate over whatever spurs the trace produced (the set varies: the south
    # spur was dropped once the ring itself reached those buildings), skipping
    # the closed ring itself.
    data = json.load(open('data/derived/plaza_roads_user.json', encoding='utf-8'))
    for name in [k for k in data['segments'] if k != 'plaza_ring']:
        pts = data['segments'][name]
        # Idempotent: a previous run already appended a join vertex. Drop it so
        # re-running does not stack degenerate zero-length tails.
        while len(pts) > 1 and _same(pts[-1], pts[-2]):
            pts.pop()
        ox, oy = xy(pts[-1][0], pts[-1][1])
        best = None
        for lon, lat in main_nodes:
            qx, qy = xy(lon, lat)
            d = math.hypot(qx - ox, qy - oy)
            if best is None or d < best[0]:
                best = (d, lon, lat)
        d, lon, lat = best
        if not _same([lon, lat], pts[-1]):
            pts.append([lon, lat])
        print(f'{name}: joined main net at {d:.1f} m')

    data['note'] += '; spurs joined to vertices of the largest OSM component'
    json.dump(data, open('data/derived/plaza_roads_user.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('-> data/derived/plaza_roads_user.json')


if __name__ == '__main__':
    main()

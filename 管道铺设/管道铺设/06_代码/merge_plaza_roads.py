"""Merge the user-traced plaza roads into the road network and rebuild the bundle.

The plaza ring road exists on the ground (visible in AMap imagery) but is absent
from OSM, which is why the three colleges on the plaza were snapping 150-220 m
away. This script:

  1. loads data/derived/plaza_roads_user.json (hand-traced, WGS-84)
  2. appends those polylines to data/raw/roads.json as synthetic highway=service
     ways, tagging them source=user_trace so they never pass as OSM data
  3. re-runs the pipeline by delegating to build_bundle_v2.py

usage: python scripts/merge_plaza_roads.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

SRC = 'data/derived/plaza_roads_user.json'
OUT = 'data/raw/roads_with_plaza.json'


def main():
    data = json.load(open(SRC, encoding='utf-8'))
    base = json.load(open('data/raw/roads.json', encoding='utf-8'))
    els = base['elements']

    # drop any earlier synthetic segments so re-running stays idempotent
    els = [e for e in els if not (e.get('tags') or {}).get('source') == 'user_trace']

    nid = 990000000
    added = 0
    for name, pts in data['segments'].items():
        geom = [{'lat': lat, 'lon': lon} for lon, lat in pts]
        els.append({
            'type': 'way',
            'id': nid,
            'bounds': {
                'minlat': min(g['lat'] for g in geom),
                'minlon': min(g['lon'] for g in geom),
                'maxlat': max(g['lat'] for g in geom),
                'maxlon': max(g['lon'] for g in geom),
            },
            'nodes': [],
            'geometry': geom,
            'tags': {'highway': 'service', 'name': name, 'source': 'user_trace'},
        })
        nid += 1
        added += 1

    out = dict(base)
    out['elements'] = els
    out['note'] = ('includes ' + str(added) + ' hand-traced plaza road segments '
                   '(tags.source = user_trace); everything else is OSM')
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'wrote {OUT}: {len(els)} ways ({added} traced, '
          f'{len(els) - added} OSM)')

    # point the builder at the merged file
    builder = 'scripts/build_bundle_v2.py'
    src = open(builder, encoding='utf-8').read()
    if "roads_with_plaza" not in src:
        src = src.replace("load('roads')", "load('roads_with_plaza')")
        src = src.replace('load("roads")', 'load("roads_with_plaza")')
        open(builder, 'w', encoding='utf-8').write(src)
        print('patched', builder, 'to use roads_with_plaza')
    else:
        print(builder, 'already uses roads_with_plaza')


if __name__ == '__main__':
    main()

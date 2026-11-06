# -*- coding: utf-8 -*-
"""Patch viz_25d.py: draw service connections (接入点) + per-floor risers.

Changes:
  1. read pipeline_bundle_conn.json (has service_connections)
  2. draw a lateral pipe from the road tap to each building's footprint edge
  3. draw a tee marker (接入点) at the road tap with its DN label
  4. draw a vertical riser inside each building, with a small outlet marker at
     every floor elevation and the floor count called out
  5. richer tooltip: lateral length, riser height, per-floor schedule

Run: python scripts/patch_viz_service.py  (edits viz_25d.py in place)
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, 'scripts', 'viz_25d.py')

src = io.open(TARGET, encoding='utf-8').read()

# ---------------------------------------------------------------- 1. bundle
src = src.replace(
    "BUNDLE = os.path.join(ROOT, 'data', 'derived', 'pipeline_bundle.json')",
    "BUNDLE = os.path.join(ROOT, 'data', 'derived', 'pipeline_bundle_conn.json')")
src = src.replace(
    '数据源：data/derived/pipeline_bundle.json（由 scripts/build_bundle_v2.py 以',
    '数据源：data/derived/pipeline_bundle_conn.json（build_bundle_v2.py + add_service_points.py，以')

# ---------------------------------------------------------------- 2. helpers
HELPERS = '''
# ---------------------------------------------------------------- connections
DN_ACTUAL = {'DN50': 50, 'DN32': 32}


def svc_geometry(d, proj):
    """Build the service-connection layer: laterals, taps, risers, outlets."""
    out = []
    for c in d.get('service_connections') or []:
        tap = c['road_tap']
        edge = c['edge_point']
        out.append(dict(
            name=c['name'], short=c['short'], cat=c['cat'],
            tap=tap, edge=edge,
            lateral=c['lateral_m'], levels=c['levels'],
            riser=c['riser_h_m'], road=c.get('road_name') or c.get('road_hw') or '',
            floors=c.get('floors') or []))
    return out

'''
src = src.replace('def main():', HELPERS + 'def main():', 1)

# ---------------------------------------------------------------- 3. load
src = src.replace(
    "    src = proj(d['meta']['source']['lat'], d['meta']['source']['lon'])",
    "    src = proj(d['meta']['source']['lat'], d['meta']['source']['lon'])\n"
    "    svcs = svc_geometry(d, proj)")

# ---------------------------------------------------------------- 4. draw
DRAW = '''
    # ---------- service connections: lateral + tap + riser + outlets --------
    svc_svg, tap_svg = [], []
    for c in svcs:
        tx, ty = c['tap']
        ex, ey = c['edge']
        # lateral: dashed thin line from the road tee to the building wall
        a, b = S(tx, ty, 0.5), S(ex, ey, 0.5)
        svc_svg.append(
            '<line class="sl" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
            'stroke="#7fe3ff" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.85">'
            '<title>%s\\n接户支管 %.1f m（沿自 %s）</title></line>'
            % (a[0], a[1], b[0], b[1], esc(c['short']), c['lateral'], esc(c['road'] or '-')))
        # tee at the road
        tap_svg.append('<circle cx="%.1f" cy="%.1f" r="4.2" fill="#0a1a22" '
                       'stroke="#7fe3ff" stroke-width="1.6"/>' % (a[0], a[1]))
        # riser: vertical line from ground to roof at the building wall point
        r0 = S(ex, ey, 0.2)
        r1 = S(ex, ey, c['riser'])
        svc_svg.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#ffe08a" '
            'stroke-width="2" stroke-linecap="round" opacity="0.9">'
            '<title>%s\\n立管 DN32 · %.1f m（%d 层）</title></line>'
            % (r0[0], r0[1], r1[0], r1[1], esc(c['short']), c['riser'], c['levels']))
        # outlet marker per floor on the riser
        for f in c['floors']:
            o = S(ex, ey, f['elev_m'])
            tap_svg.append('<circle cx="%.1f" cy="%.1f" r="1.9" fill="#ffe08a"/>'
                           % (o[0], o[1]))
        # 接入点 label at the tee, tiny
        tap_svg.append(
            '<text x="%.1f" y="%.1f" font-size="9" fill="#7fe3ff" text-anchor="middle" '
            'opacity="0.0" class="taplb">接入点</text>' % (a[0], a[1] + 12))

'''
src = src.replace("    sx, sy = S(src[0], src[1], 0.6)",
                  DRAW + "    sx, sy = S(src[0], src[1], 0.6)")

# ---------------------------------------------------------------- 5. tooltip
src = src.replace(
    """    meta_js = json.dumps([
        {'name': b['name'], 'cat': CAT_NAME.get(b['cat'], b['cat']),
         'levels': b['levels'] or '-', 'area': round(b['area']),
         'demand': round(b['demand']), 'src': b['src']} for b in bld],
        ensure_ascii=False)""",
    """    svc_by_name = {c['name']: c for c in svcs}
    meta_rows = []
    for b in bld:
        c = svc_by_name.get(b['name'])
        meta_rows.append({
            'name': b['name'], 'cat': CAT_NAME.get(b['cat'], b['cat']),
            'levels': b['levels'] or '-', 'area': round(b['area']),
            'demand': round(b['demand']), 'src': b['src'],
            'lateral': (c['lateral'] if c else None),
            'riser': (c['riser'] if c else None),
            'road': (c['road'] if c else '')})
    meta_js = json.dumps(meta_rows, ensure_ascii=False)""")

src = src.replace(
    """    tip.innerHTML = '<b>' + b.name + '</b><br>' +
      '<span>' + b.cat + ' · ' + b.levels + ' 层 · 底面积 ' + b.area + ' m²<br>' +
      '日用水 ' + b.demand + ' L/d · 几何来源 ' + (b.src === 'OSM' ? 'OSM' : '影像量测') + '</span>';""",
    """    let h = '<b>' + b.name + '</b><br>' +
      '<span>' + b.cat + ' · ' + b.levels + ' 层 · 底面积 ' + b.area + ' m²<br>' +
      '日用水 ' + b.demand + ' L/d · 几何来源 ' + (b.src === 'OSM' ? 'OSM' : '影像量测');
    if (b.lateral != null) {
      h += '<br><em style="color:#7fe3ff;font-style:normal">接入点：接自 ' +
           (b.road || '路网') + '，支管 ' + b.lateral.toFixed(1) + ' m</em>' +
           '<br><em style="color:#ffe08a;font-style:normal">立管 ' + b.riser.toFixed(1) +
           ' m，每层设出水口（1F DN50 / 2F 以上 DN32）</em>';
    } else {
      h += '<br><em style="color:#8b98a8;font-style:normal">不作供水目标（无接户）</em>';
    }
    tip.innerHTML = h + '</span>';""")

# ---------------------------------------------------------------- 6. svg layer
src = src.replace(
    '  <g id="g-blds">%(body)s</g>',
    '  <g id="g-blds">%(body)s</g>\n'
    '  <g id="g-svc">%(svc)s</g>\n'
    '  <g id="g-tap">%(taps)s</g>')
src = src.replace(
    "        body='\\n'.join(body), sx=sx, sy=sy, stats=stat_html,",
    "        body='\\n'.join(body), sx=sx, sy=sy, stats=stat_html,\n"
    "        svc='\\n'.join(svc_svg), taps='\\n'.join(tap_svg),")

# ---------------------------------------------------------------- 7. stats + legend
src = src.replace(
    "        ('估算造价', '%.1f 万元' % (st['cost_est_yuan'] / 10000)),\n    ]",
    "        ('估算造价', '%.1f 万元' % (st['cost_est_yuan'] / 10000)),\n"
    "        ('接户点（接入点）', '%d 处' % st.get('n_service_connections', 0)),\n    ]")

src = src.replace(
    '  <div id="bar">%(legend)s<span class="sep"></span>%(cat_leg)s</div>',
    '  <div id="bar">%(legend)s<span class="sep"></span>%(cat_leg)s'
    '<span class="sep"></span>'
    '<span class="lg"><i style="background:#7fe3ff;height:2px"></i>接户支管</span>'
    '<span class="lg"><i style="background:#ffe08a;height:10px;width:2px"></i>立管/楼层出水口</span>'
    '</div>')

# ---------------------------------------------------------------- 8. header note
src = src.replace(
    '    <span class="warn">※ 校园北侧圆形广场一带 OSM 未标注道路，该区学院接路距离达 150~220 m\n'
    '    （真实校园楼前必有路，属底图数据缺失，非算法误差）；无名附属建筑不作供水目标</span>',
    '    <span class="warn">※ 每个供水目标均给出了接户点：青色虚线段=从路边接入点引至楼体的支管，'
    '楼体上的黄色竖线=立管，其上的小点=各层出水口（层高 3.2 m）<br>\n'
    '    ※ 圆形广场环形路在 OSM 中缺失，已按高德影像补描，并在图例中标注为补描段；'
    '无名附属建筑不作供水目标</span>')

io.open(TARGET, 'w', encoding='utf-8').write(src)
print('patched', TARGET)

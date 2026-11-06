# -*- coding: utf-8 -*-
"""2.5D 等轴测管道方案图（单文件 HTML + SVG）。

数据源：data/derived/pipeline_bundle_conn.json（build_bundle_v2.py + add_service_points.py，以
scripts/groups.py 的 72 组注册表为真源生成）。

特性：
  * 等轴测投影，建筑按层高挤出，画家算法排序，侧面按朝向明暗
  * 管道按管径着色 + 线宽，铺设层级做生长动画，水流虚线动画
  * 建筑短名标注 + 引线，做防重叠避让
  * 悬停显示楼名 / 类别 / 层数 / 面积 / 日用水量
  * 平面 / 立体视图切换

Run: python scripts/viz_25d.py
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, 'data', 'derived', 'pipeline_bundle_conn.json')
OUT = os.path.join(ROOT, 'docs', 'fig', 'viz_25d.html')

THETA = math.radians(-14.0)   # 平面旋转 -14°，配合指北针，画布利用率最好
TILT = 0.80

DN_COLOR = {
    350: '#7b1fa2', 300: '#ab47bc', 250: '#d81b60', 200: '#e64a19',
    150: '#ef6c00', 125: '#f9a825', 100: '#9ccc65', 80: '#43a047',
    65: '#00897b', 50: '#29b6f6', 40: '#90a4ae', 32: '#b0bec5',
}

CAT_FILL = {
    'dorm': '#e8a33d', 'canteen': '#e06c75', 'teaching': '#61afef',
    'college': '#c678dd', 'library': '#56b6c2', 'lab': '#98c379',
    'office': '#d19a66', 'activity': '#e5c07b', 'art': '#f0a3c0',
    'service': '#9aa5b1', 'utility': '#7f8c99', 'sports': '#4dd0e1',
    'other': '#5c6370', 'workshop': '#8d6e63',
}
CAT_NAME = {
    'dorm': '学生公寓', 'canteen': '食堂餐厅', 'teaching': '教学楼',
    'college': '学院楼', 'library': '图书馆', 'lab': '实验楼',
    'office': '办公楼', 'activity': '活动中心', 'art': '艺术类',
    'service': '服务设施', 'utility': '市政设施', 'sports': '体育场馆',
    'other': '其他', 'workshop': '车间',
}
ROAD_W = {'trunk': 5, 'secondary': 4.5, 'tertiary': 3.6, 'unclassified': 3,
          'residential': 2.6, 'service': 2.2, 'cycleway': 1.6,
          'footway': 1.4, 'path': 1.2}



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

def main():
    with open(BUNDLE, encoding='utf-8') as f:
        d = json.load(f)
    lat0, lon0 = d['meta']['origin']
    klat = d['meta']['m_per_deg_lat']
    klon = d['meta']['m_per_deg_lon']

    def proj(lat, lon):
        return (lon - lon0) * klon, (lat - lat0) * klat

    def iso(x, y, z=0.0):
        xr = x * math.cos(THETA) - y * math.sin(THETA)
        yr = x * math.sin(THETA) + y * math.cos(THETA)
        return xr, -yr * TILT - z

    # ---------- geometry ----------
    bld = []
    for b in d['buildings']:
        raw_parts = b.get('parts') or [b['footprint']]
        parts = [[proj(p[1], p[0]) for p in part] for part in raw_parts if len(part) >= 3]
        if not parts:
            continue
        pts = parts[0]
        if len(pts) < 3:
            continue
        h = float(b.get('height') or (b.get('levels') or 3) * 3.2)
        bld.append(dict(name=b['name'], short=b.get('short') or b['name'],
                        cat=b['cat'], h=h, pts=pts, parts=parts, area=b.get('area', 0),
                        levels=b.get('levels'), demand=b.get('demand', 0),
                        src=b.get('src'), verified=b.get('verified')))

    roads = []
    for r in d['roads']:
        pts = [proj(p[1], p[0]) for p in r['pts']]
        if len(pts) >= 2:
            roads.append(dict(hw=r['hw'], pts=pts))

    pipes = []
    for p in d['pipes']:
        if p['length'] < 1.0:
            continue
        pipes.append(dict(a=proj(p['a'][1], p['a'][0]), b=proj(p['b'][1], p['b'][0]),
                          dn=p['dn'], q=p.get('q_ls', 0), L=p['length'],
                          order=p.get('order', 1)))

    src = proj(d['meta']['source']['lat'], d['meta']['source']['lon'])
    svcs = svc_geometry(d, proj)

    # ---------- frame: fit buildings + source ----------
    bx = [p[0] for b in bld for p in b['pts']] + [src[0]]
    by = [p[1] for b in bld for p in b['pts']] + [src[1]]
    cx, cy = (min(bx) + max(bx)) / 2.0, (min(by) + max(by)) / 2.0
    half = max(max(bx) - min(bx), max(by) - min(by)) / 2.0 + 60.0

    clipped = []
    for r in roads:
        cur = []
        for (x, y) in r['pts']:
            if abs(x - cx) <= half and abs(y - cy) <= half:
                cur.append((x, y))
            else:
                if len(cur) >= 2:
                    clipped.append(dict(hw=r['hw'], pts=cur))
                cur = []
        if len(cur) >= 2:
            clipped.append(dict(hw=r['hw'], pts=cur))
    roads = clipped

    allp = []
    for b in bld:
        for (x, y) in b['pts']:
            allp.append(iso(x, y, 0))
            allp.append(iso(x, y, b['h']))
    for r in roads:
        for (x, y) in r['pts']:
            allp.append(iso(x, y, 0))
    allp.append(iso(src[0], src[1], 0))
    us = [p[0] for p in allp]
    vs = [p[1] for p in allp]
    pad = 56
    umin, umax = min(us) - pad, max(us) + pad
    vmin, vmax = min(vs) - pad, max(vs) + pad
    W, H = umax - umin, vmax - vmin

    def S(x, y, z=0.0):
        u, v = iso(x, y, z)
        return round(u - umin, 1), round(v - vmin, 1)

    # ---------- ground ----------
    ground = []
    for r in roads:
        pts = ' '.join('%.1f,%.1f' % S(x, y) for x, y in r['pts'])
        ground.append('<polyline points="%s" fill="none" stroke="#333f4d" stroke-width="%.1f" '
                      'stroke-linecap="round" stroke-linejoin="round"/>'
                      % (pts, ROAD_W.get(r['hw'], 2)))

    # ---------- buildings ----------
    for b in bld:
        xs = [p[0] for p in b['pts']]
        ys = [p[1] for p in b['pts']]
        b['cx'] = sum(xs) / len(xs)
        b['cy'] = sum(ys) / len(ys)
        b['depth'] = iso(b['cx'], b['cy'], 0)[1]
    bld.sort(key=lambda z: z['depth'])

    body, spans = [], []
    for idx, b in enumerate(bld):
        fill = CAT_FILL.get(b['cat'], '#6b7280')
        for poly in b['parts']:
            edges = []
            for i in range(len(poly)):
                x1, y1 = poly[i]
                x2, y2 = poly[(i + 1) % len(poly)]
                edges.append(((iso(x1, y1)[1] + iso(x2, y2)[1]) / 2, x1, y1, x2, y2))
            edges.sort(reverse=True)
            for dep, x1, y1, x2, y2 in edges:
                a1, a2 = S(x1, y1, 0), S(x2, y2, 0)
                a3, a4 = S(x2, y2, b['h']), S(x1, y1, b['h'])
                shade = 0.42 + 0.52 * abs(math.cos(math.atan2(y2 - y1, x2 - x1) - THETA))
                body.append('<polygon data-i="%d" class="bp" points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" '
                            'fill="%s" fill-opacity="%.2f" stroke="#0b0f14" stroke-width="0.6"/>'
                            % (idx, a1[0], a1[1], a2[0], a2[1], a3[0], a3[1], a4[0], a4[1], fill, shade))
            top = ' '.join('%.1f,%.1f' % S(x, y, b['h']) for x, y in poly)
            body.append('<polygon data-i="%d" class="bp" points="%s" fill="%s" stroke="#eef2f7" '
                        'stroke-width="0.9" stroke-opacity="0.6"/>' % (idx, top, fill))
        spans.append((idx, b['cx'], b['cy'], b['h']))

    # ---------- labels with collision avoidance ----------
    cand = []
    for idx, bx0, by0, bh in spans:
        b = bld[idx]
        u, v = S(bx0, by0, bh)
        cand.append((v, u, idx, b))
    cand.sort()

    placed = []
    for v, u, idx, b in cand:
        label = b['short']
        unnamed = label.startswith('U') and label[1:].isdigit()
        # CJK glyphs are a full em wide, latin ones about 0.55 em -- estimating
        # everything at one advance made mixed labels under-reserve space and
        # neighbouring plates overlapped.
        fs = 10 if unnamed else 13
        wpx = sum(fs if ord(ch) > 0x2E80 else fs * 0.56 for ch in label) + 12
        # prefer sitting right on the roof top, then step upward; sideways last.
        # unnamed shed-like buildings get their tag pushed clear of the roof so
        # the little dark plate does not sit on top of the tiny building.
        if unnamed:
            trials = [(u, v - 20), (u + 30, v - 6), (u - 30, v - 6),
                      (u, v - 34), (u, v + 12)]
        else:
            trials = [(u, v + 4), (u, v - 14), (u, v - 26), (u, v + 20), (u, v - 38),
                      (u + 38, v), (u - 38, v), (u + 38, v - 18), (u - 38, v - 18),
                      (u, v - 50), (u, v + 36)]
        chosen = None
        for (tu, tv) in trials:
            box = (tu - wpx / 2, tv - 11, tu + wpx / 2, tv + 5)
            if box[0] < 4 or box[2] > W - 4 or box[1] < 4 or box[3] > H - 4:
                continue
            if all(not (box[0] < o[2] and box[2] > o[0] and box[1] < o[3] and box[3] > o[1])
                   for o in placed):
                chosen = (tu, tv, box)
                break
        if chosen is None:
            continue
        placed.append(chosen[2])
        tu, tv = chosen[0], chosen[1]
        anc = ''
        if abs(tv - v) > 16 or abs(tu - u) > 10:
            anc = ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#9db0c6" '
                   'stroke-width="0.7" stroke-dasharray="2.5,2.5" opacity="0.75"/>'
                   % (tu, tv + 3, u, v + 1))
        if unnamed:
            # lighter, smaller plate: these are background sheds, not plan items
            body.append(anc + '<rect x="%.1f" y="%.1f" width="%.1f" height="12" rx="2" '
                              'fill="#0a1119" fill-opacity="0.34"/>'
                              % (tu - wpx / 2, tv - 9, wpx))
            body.append('<text x="%.1f" y="%.1f" class="bl bu" data-i="%d" text-anchor="middle" '
                        'font-size="10">%s</text>' % (tu, tv - 1, idx, esc(label)))
        else:
            # dark backing plate keeps the text readable on any roof colour
            body.append(anc + '<rect x="%.1f" y="%.1f" width="%.1f" height="15" rx="3" '
                              'fill="#050a10" fill-opacity="0.62"/>'
                              % (tu - wpx / 2, tv - 11, wpx))
            body.append('<text x="%.1f" y="%.1f" class="bl" data-i="%d" text-anchor="middle" '
                        'font-size="13">%s</text>' % (tu, tv, idx, esc(label)))

    # ---------- pipes ----------
    pipe_svg = []
    for p in sorted(pipes, key=lambda z: -z['dn']):
        s1, s2 = S(p['a'][0], p['a'][1], 0.6), S(p['b'][0], p['b'][1], 0.6)
        w = 1.8 + (p['dn'] - 40) / 310.0 * 9.0
        col = DN_COLOR.get(p['dn'], '#90a4ae')
        pipe_svg.append(
            '<line class="pl" data-order="%d" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
            'stroke="%s" stroke-width="%.1f" stroke-linecap="round" opacity="0.95">'
            '<title>DN%d · %.1f m · %.2f L/s</title></line>'
            % (p['order'], s1[0], s1[1], s2[0], s2[1], col, w, p['dn'], p['L'], p['q']))


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
            '<title>%s\n接户支管 %.1f m（沿自 %s）</title></line>'
            % (a[0], a[1], b[0], b[1], esc(c['short']), c['lateral'], esc(c['road'] or '-')))
        # tee at the road
        tap_svg.append('<circle cx="%.1f" cy="%.1f" r="4.2" fill="#0a1a22" '
                       'stroke="#7fe3ff" stroke-width="1.6"/>' % (a[0], a[1]))
        # riser: vertical line from ground to roof at the building wall point.
        # Start at z=0 and give it a warm base dot so it reads as "rising out of
        # the building", not as a short line floating beside it.
        r0 = S(ex, ey, 0.0)
        r1 = S(ex, ey, c['riser'])
        tap_svg.append('<circle cx="%.1f" cy="%.1f" r="3.0" fill="#ffe08a" '
                       'fill-opacity="0.55"/>' % (r0[0], r0[1]))
        svc_svg.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#ffe08a" '
            'stroke-width="2" stroke-linecap="round" opacity="0.9">'
            '<title>%s\n立管 DN32 · %.1f m（%d 层）</title></line>'
            % (r0[0], r0[1], r1[0], r1[1], esc(c['short']), c['riser'], c['levels']))
        # outlet marker per floor on the riser
        for f in c['floors']:
            o = S(ex, ey, f['elev_m'])
            tap_svg.append('<circle cx="%.1f" cy="%.1f" r="1.9" fill="#ffe08a"/>'
                           % (o[0], o[1]))
        # 接入点 marker at the tee: hover shows the full floor schedule
        sched = ' / '.join('%dF %s' % (f['floor'], f['fn']) for f in c['floors'])
        tap_svg.append(
            '<g class="tap"><circle cx="%.1f" cy="%.1f" r="4.2" fill="#0a1a22" '
            'stroke="#7fe3ff" stroke-width="1.6"/>'
            '<circle cx="%.1f" cy="%.1f" r="9" fill="#7fe3ff" fill-opacity="0.10"/>'
            '<title>接入点 %s\n接自 %s，支管 %.1f m\n立管 DN32 %.1f m（%d 层）\n'
            '出水口：%s</title></g>'
            % (a[0], a[1], a[0], a[1], esc(c['short']),
               esc(c['road'] or c['road_hw'] or '校内路'), c['lateral'],
               c['riser'], c['levels'], sched))

    sx, sy = S(src[0], src[1], 0.6)

    # ---------- stats ----------
    st = d['stats']
    stats_rows = [
        ('建筑群（参与计算）', '%d 个' % st['n_buildings']),
        ('  其中 OSM 轮廓', '%d 个' % st['n_osm']),
        ('  其中影像量测', '%d 个' % st['n_measured']),
        ('供水目标', '%d 个' % st['n_targets']),
        ('基底面积合计', '%.1f 万 m²' % (st['total_area_m2'] / 10000)),
        ('MST 加权总长', '%.1f m' % st['mst_length_m']),
        ('管道实长', '%.1f m' % st['pipe_length_m']),
        ('直线MST 对照', '%.1f m' % st['straight_mst_length_m']),
        ('总用水量', '%.1f m³/d' % st['total_demand_m3d']),
        ('设计流量', '%.2f L/s' % st['q_total_ls']),
        ('主干管径', 'DN%d' % st['main_dn']),
        ('最大树深', '%d 层' % st['max_depth']),
        ('估算造价', '%.1f 万元' % (st['cost_est_yuan'] / 10000)),
        ('接户点（接入点）', '%d 处' % st.get('n_service_connections', 0)),
    ]
    stat_html = ''.join('<div class="row"><span class="k">%s</span><span class="v">%s</span></div>'
                        % (k, v) for k, v in stats_rows)

    legend = ''.join('<span class="lg"><i style="background:%s"></i>DN%d</span>' % (c, dn)
                     for dn, c in sorted(DN_COLOR.items(), reverse=True) if dn >= 40)
    cat_leg = ''.join('<span class="lg"><i class="sq" style="background:%s"></i>%s</span>'
                      % (c, CAT_NAME.get(k, k)) for k, c in CAT_FILL.items() if k != 'other')

    svc_by_name = {c['name']: c for c in svcs}
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
    meta_js = json.dumps(meta_rows, ensure_ascii=False)

    # ---- north arrow + scale bar (drawn in screen space) ----
    # a unit vector pointing north in local metres maps to screen via iso()
    n0 = iso(0.0, 0.0, 0.0)
    n1 = iso(0.0, 1.0, 0.0)
    ndx, ndy = n1[0] - n0[0], n1[1] - n0[1]
    nlen = math.hypot(ndx, ndy) or 1.0
    ndx, ndy = ndx / nlen, ndy / nlen
    NAX, NAY, NR = 84.0, 80.0, 30.0
    arrow = ('<g id="north" transform="translate(%.1f,%.1f)">'
             '<circle r="%.1f" fill="#0b1017" fill-opacity="0.72" stroke="#3a4756" stroke-width="1"/>'
             '<line x1="0" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#ffd479" stroke-width="2.2" '
             'stroke-linecap="round"/>'
             '<polygon points="0,-18 %.1f,12 0,5 %.1f,12" fill="#ffd479"/>'
             '<text x="0" y="30" text-anchor="middle" font-size="12" fill="#ffd479">北</text>'
             '</g>' % (NAX, NAY, NR + 8, NR * 0.82, ndx * (NR - 4), ndy * (NR - 4),
                       -ndx * 3.4, ndx * 3.4))
    # scale bar: 100 m along the (rotated) east axis at ground level
    e0 = iso(0.0, 0.0, 0.0)
    e1 = iso(100.0, 0.0, 0.0)
    edx, edy = e1[0] - e0[0], e1[1] - e0[1]
    el = math.hypot(edx, edy) or 1.0
    # scale bar sits at the bottom-left, but flipped above the source marker
    SBX, SBY = 40.0, H - 40.0
    sbar = ('<g id="scalebar" transform="translate(%.1f,%.1f)">'
            '<line x1="0" y1="0" x2="%.1f" y2="%.1f" stroke="#dbe3ee" stroke-width="2"/>'
            '<line x1="0" y1="-4" x2="0" y2="4" stroke="#dbe3ee" stroke-width="2"/>'
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#dbe3ee" stroke-width="2"/>'
            '<text x="%.1f" y="%.1f" font-size="12" fill="#dbe3ee" text-anchor="middle">100 m</text>'
            '</g>' % (SBX, SBY, edx, edy, edx, edy, edx, edy, edx / 2.0, edy / 2.0 + 16))

    # place the source marker's caption so it never runs into the legend strip
    sx0 = min(max(sx - 98, 8), W - 204)
    sy0 = sy - 30 if sy - 30 > 8 else sy + 12
    sxt = sx0 + 98.0
    syt = sy0 + 12.5

    html = TEMPLATE % dict(
        W=W, H=H, ground='\n'.join(ground), pipes='\n'.join(pipe_svg),
        body='\n'.join(body), sx=sx, sy=sy, sx0=sx0, sy0=sy0, sxt=sxt, syt=syt,
        stats=stat_html,
        svc='\n'.join(svc_svg), taps='\n'.join(tap_svg),
        legend=legend, cat_leg=cat_leg, meta=meta_js,
        north=arrow, sbar=sbar,
        n_bld=st['n_buildings'], n_labels=len(placed), n_targets=st['n_targets'],
        n_osm=st['n_osm'], n_meas=st['n_measured'],
        gen=d['meta']['generated'])

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('saved %s  %.0f x %.0f  buildings=%d labels=%d'
          % (OUT, W, H, len(bld), len(placed)))


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>燕山大学西校区管道铺设 · 2.5D 方案图</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; background:#080b10; color:#dbe3ee;
         font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif; }
  header { padding:18px 26px 10px; }
  h1 { margin:0; font-size:22px; letter-spacing:.5px; }
  .sub { color:#8b98a8; font-size:13px; margin-top:6px; line-height:1.7; }\n  .warn { color:#c9a227; font-size:12px; }
  .wrap { position:relative; }
  svg { display:block; width:100%%; height:auto; }
  .bl { fill:#e9f0f8; paint-order:stroke; stroke:#080b10; stroke-width:2.6;
        stroke-linejoin:round; pointer-events:none; }
  .bl.bu { fill:#8f9fb2; stroke-width:1.8; opacity:0.85; }
  .bp { cursor:pointer; }
  .bp:hover { filter:brightness(1.35); }
  #panel { position:fixed; right:18px; top:18px; width:262px;
           background:rgba(13,17,23,.94); border:1px solid #26303d;
           border-radius:10px; padding:14px 16px; font-size:13px; }
  #panel h2 { margin:0 0 10px; font-size:14px; color:#9fb3c8; font-weight:600;
              display:flex; justify-content:space-between; align-items:center; }
  #pbtn { background:#1b2530; color:#9fb3c8; border:1px solid #2b3542; border-radius:5px;
          width:22px; height:20px; line-height:1; cursor:pointer; font-size:14px;
          font-family:inherit; padding:0; }
  #panel.collapsed #pbody { display:none; }
  #panel.collapsed { width:auto; padding:10px 12px; }
  .row { display:flex; justify-content:space-between; padding:3px 0;
         border-bottom:1px dashed #1d2530; }
  .row:last-child { border:0; }
  .k { color:#8291a3; } .v { color:#eaf2fb; font-variant-numeric:tabular-nums; }
  #bar { position:static; margin:0 auto 16px; background:rgba(13,17,23,.95);
         border:1px solid #26303d; border-radius:10px; padding:10px 14px;
         font-size:11.5px; display:flex; gap:11px; align-items:center;
         flex-wrap:wrap; justify-content:center; max-width:1420px; width:calc(100%% - 36px); }
  #bar .sep { width:1px; height:14px; background:#2b3542; }
  .lg { display:inline-flex; align-items:center; gap:4px; color:#a9b6c6; white-space:nowrap; }
  .lg i { width:14px; height:4px; border-radius:2px; display:inline-block; }
  .lg i.sq { width:9px; height:9px; border-radius:2px; }
  #tip { position:fixed; pointer-events:none; background:rgba(8,12,18,.97);
         border:1px solid #33404f; border-radius:8px; padding:8px 11px;
         font-size:12px; line-height:1.6; opacity:0; transition:opacity .12s;
         max-width:300px; z-index:9; }
  #tip b { color:#ffd479; }
  #tip span { color:#93a3b6; }
  #ctl { position:fixed; right:18px; top:calc(18px + 372px); display:flex;
         flex-direction:column; gap:8px; z-index:8; }
  #ctl button { width:100%%; }
  #ctl button { background:#131a24; color:#c9d6e5; border:1px solid #2b3542;
                border-radius:8px; padding:8px 14px; font-size:12px; cursor:pointer;
                font-family:inherit; }
  #ctl button:hover { background:#1b2530; border-color:#3c4a5c; }
  #ctl button.on { background:#20476b; border-color:#3873a8; color:#eaf2fb; }
</style></head>
<body>
<header>
  <h1>燕山大学西校区 · 给水管道铺设方案图（2.5D 等轴测）</h1>
  <div class="sub">
    最小生成树（Kruskal）沿真实路网求解 &nbsp;·&nbsp; 图上 %(n_bld)d 个建筑群，其中
    %(n_targets)d 个为供水目标（OSM 轮廓 %(n_osm)d + 影像量测 %(n_meas)d）<br>
    数据源：OpenStreetMap（ODbL）+ 高德卫星影像量测 + 校方官方地图核对 &nbsp;·&nbsp;
    坐标 WGS-84 &nbsp;·&nbsp; 生成于 %(gen)s<br>
    <span class="warn">※ 每个供水目标均给出了接户点：青色虚线段=从路边接入点引至楼体的支管，楼体上的黄色竖线=立管，其上的小点=各层出水口（层高 3.2 m）<br>
    ※ 圆形广场环形路在 OSM 中缺失，已按高德影像补描，并在图例中标注为补描段；无名附属建筑不作供水目标</span>
  </div>
</header>
<div class="wrap">
<svg id="map" viewBox="0 0 %(W).1f %(H).1f" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0b1017"/><stop offset="1" stop-color="#121a25"/>
    </linearGradient>
    <filter id="glow" x="-50%%" y="-50%%" width="200%%" height="200%%">
      <feGaussianBlur stdDeviation="2.6" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="softglow" x="-50%%" y="-50%%" width="200%%" height="200%%">
      <feGaussianBlur stdDeviation="1.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect x="0" y="0" width="%(W).1f" height="%(H).1f" fill="url(#sky)"/>
  <g id="g-roads">%(ground)s</g>
  <g id="g-pipes" filter="url(#glow)">%(pipes)s</g>
  <g id="g-blds">%(body)s</g>
  <g id="g-svc">%(svc)s</g>
  <g id="g-tap">%(taps)s</g>
  <g id="g-hud">%(north)s%(sbar)s</g>
  <g id="g-src">
    <circle cx="%(sx).1f" cy="%(sy).1f" r="11" fill="#ffcc33" opacity=".28"/>
    <circle cx="%(sx).1f" cy="%(sy).1f" r="4.5" fill="#ffd54f"/>
    <rect x="%(sx0).1f" y="%(sy0).1f" width="196" height="17" rx="3"
          fill="#0a0f16" fill-opacity="0.78" stroke="#ffd54f" stroke-opacity="0.55" stroke-width="0.8"/>
    <text x="%(sxt).1f" y="%(syt).1f" fill="#ffd54f" font-size="12" text-anchor="middle"
          style="paint-order:stroke;stroke:#080b10;stroke-width:2.4">市政给水接入点（假设）</text>
  </g>
</svg>
</div>
<div id="panel"><h2>方案统计 <button id="pbtn" title="收起/展开">−</button></h2><div id="pbody">%(stats)s</div></div>
<div id="bar">%(legend)s<span class="sep"></span>%(cat_leg)s<span class="sep"></span>
<span class="lg"><i style="background:#7fe3ff;height:2px"></i>接户支管</span>
<span class="lg"><i style="background:#ffe08a;height:10px;width:2px"></i>立管/楼层出水口</span></div>
<div id="ctl">
  <button id="btn-iso" class="on">立体</button>
  <button id="btn-flow" class="on">水流</button>
  <button id="btn-grow">重播铺设</button>
</div>
<div id="tip"></div>
<script>
const META = %(meta)s;
const tip = document.getElementById('tip');
document.querySelectorAll('.bp').forEach(function (el) {
  el.addEventListener('mousemove', function (e) {
    const b = META[+el.dataset.i];
    if (!b) return;
    let h = '<b>' + b.name + '</b><br>' +
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
    tip.innerHTML = h + '</span>';
    tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX + 16, innerWidth - 320) + 'px';
    tip.style.top = (e.clientY + 14) + 'px';
  });
  el.addEventListener('mouseleave', function () { tip.style.opacity = 0; });
});

// water-flow dashes on the trunk pipes
const pipes = [...document.querySelectorAll('.pl')];
pipes.forEach(function (p) {
  p.style.strokeDasharray = '';
});
let flowOn = true;
const flowLayer = document.getElementById('g-pipes');
const ghosts = pipes.map(function (p) {
  const c = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  ['x1','y1','x2','y2'].forEach(function (k) { c.setAttribute(k, p.getAttribute(k)); });
  c.setAttribute('stroke', '#ffffff');
  c.setAttribute('stroke-width', Math.max(1.6, parseFloat(p.getAttribute('stroke-width')) * 0.40));
  c.setAttribute('stroke-linecap', 'round');
  c.setAttribute('opacity', '0.92');
  c.setAttribute('stroke-dasharray', '4 16');
  c.style.animation = 'fl ' + (2.6 + Math.random() * 1.4) + 's linear infinite';
  return c;
});
ghosts.forEach(function (g) { flowLayer.appendChild(g); });
const st = document.createElement('style');
st.textContent = '@keyframes fl { to { stroke-dashoffset: -220; } }';
document.head.appendChild(st);

document.getElementById('pbtn').onclick = function () {
  const p = document.getElementById('panel');
  p.classList.toggle('collapsed');
  this.textContent = p.classList.contains('collapsed') ? '+' : '\u2212';
};

document.getElementById('btn-flow').onclick = function () {
  flowOn = !flowOn;
  this.classList.toggle('on', flowOn);
  ghosts.forEach(function (g) { g.style.display = flowOn ? '' : 'none'; });
};

// replays the lay-down animation, level by level outward from the source
document.getElementById('btn-grow').onclick = function () {
  if (!flowOn) { flowOn = true; document.getElementById('btn-flow').classList.add('on');
                 ghosts.forEach(function (g) { g.style.display = ''; }); }
  pipes.forEach(function (p) {
    const t = +p.dataset.order * 0.30;
    p.style.animation = 'none';
    p.getBoundingClientRect();
    p.style.animation = 'grow .5s ease-out ' + t + 's forwards';
    p.setAttribute('data-hide', '1');
  });
};
const st2 = document.createElement('style');
st2.textContent = '@keyframes grow { from { opacity: 0; } to { opacity: .95; } }';
document.head.appendChild(st2);
</script>
</body></html>"""


if __name__ == '__main__':
    main()

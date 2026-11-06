"""Overlay the user's hand-traced plaza roads onto the two-source campus figure.

Reference frame is exactly the one used to draw docs/fig/fig_two_source_campus.jpg:
    * base canvas = the stitched AMap z17 satellite mosaic (11 x 10 tiles), then
      blended with a dark layer (identical to fig_two_source.py)
    * a 92 px header bar is pasted on top, so
          full-figure px = mosaic px + (0, 92)
    * WGS-84 -> mosaic px is fig_two_source.sx(lon, lat), which is the mapping
      that produced the correct figure (it applies WGS-84 -> GCJ-02 first).
      Do NOT re-derive a scale factor here: doing so is what historically put
      the overlay ~400 m off.

Everything below therefore calls sx() and adds the header offset only.

Output: docs/fig/fig_user_traced_route.jpg
usage:  python scripts/fig_user_route.py
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import groups as G  # noqa: E402
import fig_two_source as F  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

HDR = 92                      # header bar height in the two-source figure
OUT = 'docs/fig/fig_user_traced_route.jpg'
SRC = 'docs/fig/fig_two_source_campus.jpg'

FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'

# user-traced road styling
USER_COL = (255, 0, 220)      # magenta
USER_HALO = (255, 255, 255)
PARK_FILL = (255, 240, 170)

# how the 5 traced ways are drawn / labelled
#   (json key, legend label, dash pattern or None)
ROAD_STYLE = {
    'plaza_ring':          ('广场环道（用户标注）', None),
    'plaza_west_approach': ('西向接入（用户标注）', None),
    'plaza_north_link':    ('北路连接（用户标注）', None),
    'plaza_east_spur':     ('东向支路（用户标注）', None),
    'plaza_south_spur':    ('南向支路（用户标注）', None),
}

# The triangular mark west of the plaza is a PARKING LOT, not a road.
# Defined in the same full-figure pixel frame as everything else.  It is drawn
# only as a light translucent fill plus a caption; it is never treated as a way.
PARK_POLY = [(1330.0, 168.0), (1330.0, 292.0), (1246.0, 268.0)]

# Ring-road geometry note -----------------------------------------------------
# The five traced ways in data/derived/plaza_roads_user.json were calibrated by
# scripts/plaza_road_trace.py against the three measured colleges:
#     X01 信息学院 (1654.7, 221.2)  X02 人工智能 (1603.5, 335.5)  X03 理学院 (1727.3, 342.9)
# Those anchors reproduce the figure exactly (checked: sx() of the
# plaza_buildings.json centres lands within ~2 px of those pixels), so sx() is
# the right mapping and no re-derivation is allowed.
#
# What the data does NOT capture is the ring's SIZE: the traced ring has
# r = 72 px around (1665, 329 M), i.e. ~90 m of ground radius, while the asphalt
# ring drawn on the imagery around the circular plaza is r ~ 100 px (~125 m).
# The ring therefore sits ~28 px (≈35 m) too tight and shows up inside the
# paving circle.  We draw the data EXACTLY as stored (the deliverable must not
# silently "fix" the user's hand trace) and only print a diagnostic below.
RING_PROBE_PX = (1665.0, 329.0, 72.0)     # mosaic px: cx, cy, expected r

CAT_COL = F.CAT_COL


def build_base():
    """Rebuild the identical two-source base canvas (mosaic + dark blend)."""
    sat = F.stitch(F.SAT_DIR)
    return Image.blend(sat, Image.new('RGB', sat.size, (12, 16, 22)), 0.42)


def load_roads():
    p = 'data/derived/plaza_roads_user.json'
    data = json.load(open(p, encoding='utf-8'))
    return data['segments']


def main():
    if os.path.exists(SRC):
        base = Image.open(SRC).convert('RGB')
        ox = oy = 0
        print('using existing', SRC, base.size)
        # The sourced figure ALREADY carries the original 92 px header, so the
        # base body starts at (0, HDR): full-figure py = sx() py + HDR, and our
        # own header must be composed onto a fresh strip instead of over it.
        oy = HDR
    else:                                        # pragma: no cover
        base = build_base()
        ox, oy = 0, HDR
        print('rebuilt base', base.size)

    W, H = base.size
    d = ImageDraw.Draw(base, 'RGBA')
    f18 = ImageFont.truetype(FONT, 18)
    f15 = ImageFont.truetype(FONT, 15)
    f14 = ImageFont.truetype(FONT, 14)

    def P(lon, lat):
        """WGS-84 -> full-figure pixel (the ONLY mapping used here)."""
        x, y = F.sx(lon, lat)
        return x + ox, y + oy

    # ------------------------------------------------------------------
    # 0. parking-lot fill (under everything else)
    # ------------------------------------------------------------------
    pk = [(x + ox, y + oy) for x, y in PARK_POLY]
    d.polygon(pk, fill=PARK_FILL + (60,), outline=(210, 170, 60, 220), width=2)

    # ------------------------------------------------------------------
    # 1. OSM roads in blue (same rule as fig_two_source.py)
    # ------------------------------------------------------------------
    roads = json.load(open('data/raw/roads.json', encoding='utf-8'))['elements']
    n_road = 0
    for el in roads:
        hw = (el.get('tags') or {}).get('highway', '')
        if hw in ('steps', 'construction'):
            continue
        geom = el.get('geometry') or []
        if len(geom) < 2:
            continue
        pts = [P(q['lon'], q['lat']) for q in geom if q]
        if len(pts) < 2:
            continue
        w = 5 if hw in ('trunk', 'secondary', 'tertiary') else 3
        d.line(pts, fill=(90, 210, 255, 210), width=w, joint='curve')
        n_road += 1
    print('osm roads drawn', n_road)

    # ------------------------------------------------------------------
    # 2. building outlines
    # ------------------------------------------------------------------
    osm = F.load_osm_buildings()
    n_osm = 0
    for g in G.GROUPS:
        if g.get('measured'):
            continue
        col = CAT_COL.get(g['cat'], (150, 150, 150))
        for wid in g.get('ways', []):
            el = osm.get(wid)
            if not el or not el.get('geometry'):
                continue
            pts = [P(p['lon'], p['lat']) for p in el['geometry'] if p]
            if len(pts) < 3:
                continue
            d.line(pts + [pts[0]], fill=col + (230,), width=2)
            n_osm += 1
    n_meas = 0
    for g in G.GROUPS:
        m = g.get('measured')
        if not m:
            continue
        x0, y0, x1, y1 = m['bbox']
        ax, ay = P(x0, y1)
        bx, by = P(x1, y0)
        xs, xe = sorted((ax, bx))
        ys, ye = sorted((ay, by))
        d.rectangle([xs, ys, xe, ye], outline=(0, 230, 190, 220), width=2)
        n_meas += 1
    print('outlines', n_osm, 'measured boxes', n_meas)

    # ------------------------------------------------------------------
    # 3. THE POINT: user-traced roads, magenta, thick, with white halo
    # ------------------------------------------------------------------
    segs = load_roads()
    labels = []
    for name, pts in segs.items():
        if len(pts) < 2:
            continue
        xy = [P(lon, lat) for lon, lat in pts]
        d.line(xy, fill=USER_HALO + (150,), width=13, joint='curve')
        d.line(xy, fill=USER_COL + (245,), width=7, joint='curve')
        for q in xy:                       # vertex dots
            d.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3],
                      fill=USER_COL + (255,), outline=(255, 255, 255, 255))
        lab = ROAD_STYLE.get(name, (name, None))[0]
        if name == 'plaza_ring':
            # put the ring caption to the right of the ring, clear of the buildings
            mx = max(q[0] for q in xy) + 220
            my = sum(q[1] for q in xy) / len(xy) - 110
        else:
            mx, my = xy[len(xy) // 2]
        labels.append((lab, mx, my, name))
        print(f'{name}: {len(pts)} pts drawn')

    # ------------------------------------------------------------------
    # 4. parking caption + traced-road captions
    # ------------------------------------------------------------------
    px = sum(q[0] for q in pk) / 3.0
    py = sum(q[1] for q in pk) / 3.0
    txt = '停车场（非道路）'
    tw = d.textlength(txt, font=f15)
    d.rectangle([px - tw / 2 - 5, py - 11, px + tw / 2 + 5, py + 11],
                fill=(60, 40, 0, 200))
    d.text((px - tw / 2, py - 9), txt, font=f15, fill=(255, 235, 150, 255))

    # avoid overlapping captions: keep an occupancy list in figure space
    taken = [pk] + [[(px - tw / 2 - 5, py - 11), (px + tw / 2 + 5, py + 11)]]

    def box_of(x, y, w, h):
        return [(x - w / 2, y - h / 2), (x + w / 2, y + h / 2)]

    # every drawn polyline, so captions never land on a magenta line
    lines = []
    for _n, _pts in segs.items():
        if len(_pts) >= 2:
            lines.append([P(lon, lat) for lon, lat in _pts])

    def seg_hits_box(p, q, bb, pad=6.0):
        x0, y0, x1, y1 = min(p[0], q[0]) - pad, min(p[1], q[1]) - pad, \
            max(p[0], q[0]) + pad, max(p[1], q[1]) + pad
        return not (bb[1][0] < x0 or bb[0][0] > x1 or bb[1][1] < y0 or bb[0][1] > y1)

    def hits_line(bb):
        for ln in lines:
            for i in range(len(ln) - 1):
                if seg_hits_box(ln[i], ln[i + 1], bb):
                    return True
        return False

    def clashes(b):
        for t in taken:
            tx = [p[0] for p in t]
            ty = [p[1] for p in t]
            if b[0][0] < max(tx) and b[1][0] > min(tx) \
               and b[0][1] < max(ty) and b[1][1] > min(ty):
                return True
        return False

    for lab, mx, my, name in labels:
        tw = d.textlength(lab, font=f14)
        w, h = tw + 10, 20
        # search outward for a slot that clears the other captions AND all the
        # traced polylines (so no caption sits on top of a magenta line)
        cand = [(mx, my)]
        for ring in (34, 56, 78, 102, 128):
            for k in range(8):
                a = math.radians(k * 45.0)
                cand.append((mx + ring * math.cos(a), my + ring * math.sin(a)))
        chosen, b, ok = (mx, my), box_of(mx, my, w, h), False
        for cx, cy in cand:
            bb = box_of(cx, cy, w, h)
            if not clashes(bb) and not hits_line(bb):
                chosen, b, ok = (cx, cy), bb, True
                break
        if not ok:
            chosen, b = (mx, my), box_of(mx, my, w, h)
        taken.append(b)
        cx, cy = chosen
        d.rectangle([b[0][0], b[0][1], b[1][0], b[1][1]],
                    fill=(45, 0, 40, 215), outline=USER_COL + (255,), width=1)
        d.text((cx - tw / 2, cy - 8), lab, font=f14, fill=(255, 160, 245, 255))

    # ------------------------------------------------------------------
    # 5. header / legend
    # ------------------------------------------------------------------
    dc = ImageDraw.Draw(base, 'RGBA')
    if HDR and oy == HDR:
        dc.rectangle([0, 0, W, HDR], fill=(10, 13, 18, 255))
        fb30 = ImageFont.truetype(FONTB, 26)
        dc.text((16, 6),
                '燕山大学西校区 · 用户标注广场道路叠加图（底图=双源合成图）',
                font=fb30, fill=(255, 255, 255))
        # legend swatches
        lx, ly = 16, 44
        # magenta = user trace
        dc.line([(lx, ly + 8), (lx + 44, ly + 8)], fill=USER_COL + (255,), width=7)
        dc.text((lx + 52, ly), '用户标注路线（5 条手描，source=user_trace）',
                font=f15, fill=(255, 170, 250))
        lx2 = 470
        dc.line([(lx2, ly + 8), (lx2 + 44, ly + 8)], fill=(90, 210, 255, 255), width=4)
        dc.text((lx2 + 52, ly), 'OSM 道路（蓝）', font=f15, fill=(150, 220, 255))
        lx3 = 690
        dc.rectangle([lx3, ly + 2, lx3 + 40, ly + 15], outline=(0, 230, 190, 255), width=2)
        dc.text((lx3 + 48, ly), '影像量测（青框）／OSM 轮廓（彩色）',
                font=f15, fill=(170, 240, 225))
        lx4 = 1090
        dc.polygon([(lx4, ly + 2), (lx4 + 16, ly + 16), (lx4, ly + 16)],
                   fill=PARK_FILL + (120,), outline=(210, 170, 60, 255), width=1)
        dc.text((lx4 + 24, ly), '停车场（非道路）', font=f15, fill=(255, 235, 150))
        dc.text((16, 66),
                '注：圆形广场环形路 OSM 缺失，由用户手工描出补入；本图仅叠加显示，不修改 04_数据 原始文件。'
                '坐标系 WGS-84（已做 GCJ-02 反解）；来源 © OpenStreetMap contributors / © 高德地图',
                font=f14, fill=(150, 170, 190))

    base.save(OUT, quality=90)
    print('saved', OUT, base.size)

    # ---- diagnostic: does the traced ring match the paved circle on imagery? --
    ring = segs.get('plaza_ring') or []
    if len(ring) >= 3:
        xy = [P(lon, lat) for lon, lat in ring]
        cx = sum(q[0] for q in xy) / len(xy)
        cy = sum(q[1] for q in xy) / len(xy)
        r = sum(math.hypot(q[0] - cx, q[1] - cy) for q in xy) / len(xy)
        m_per_px = 156543.03392 * math.cos(math.radians(39.917)) / (2 ** F.Z)
        print(f'ring centre (figure px) = ({cx:.1f}, {cy:.1f}), r = {r:.1f} px '
              f'= {r * m_per_px:.1f} m')
        print(f'    reference: the paved ring road is r ~= 145 m '
              f'(~ {145 / m_per_px:.0f} px). Deviation '
              f'{(r * m_per_px) - 145:+.1f} m.')


if __name__ == '__main__':
    main()

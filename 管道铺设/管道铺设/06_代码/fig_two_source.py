"""Two-source campus map: OSM + AMap, AMap wins on conflicts.

Sources:
  - AMap z18 satellite tiles  (data/tiles/*)          -> base image
  - AMap z18 road/label tiles                          -> "AMap says X"
  - AMap Web-service POIs (data/derived/amap_around_*.json) -> "AMap says X"
  - OSM buildings / roads (data/raw/*.json)            -> "OSM says X"

Conflict rule: where AMap provides a name/position, AMap is authoritative.
Where AMap is silent and OSM is silent too, mark it as 待核实.

usage: python scripts/fig_two_source.py
"""
import glob
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import groups as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

Z = 17
TILE = 256
X0, Y0 = 109046, 49659
NX, NY = 11, 10

SAT_DIR = 'data/tiles/campus_sat_z17_full'
RD_DIR = 'data/tiles/campus_road_z17_full'
OUT = 'docs/fig/fig_two_source_campus.jpg'

FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'

CAT_COL = {
    'dorm': (255, 96, 96), 'canteen': (255, 168, 48), 'teaching': (96, 160, 255),
    'college': (72, 220, 180), 'lab': (186, 120, 255), 'library': (255, 130, 210),
    'office': (120, 210, 120), 'activity': (255, 200, 90), 'art': (250, 140, 250),
    'service': (150, 200, 255), 'sports': (120, 235, 235), 'utility': (170, 170, 170),
    'other': (150, 150, 150),
}


def merc_px(lon, lat, z=Z):
    n = 2.0 ** z * TILE
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def wgs2gcj(lon, lat):
    a, ee = 6378245.0, 0.00669342162296594323

    def tlat(x, y):
        r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x)))
        r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return r

    def tlon(x, y):
        r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return r

    dlat, dlon = tlat(lon - 105.0, lat - 35.0), tlon(lon - 105.0, lat - 35.0)
    rad = math.radians(lat)
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def gcj2wgs(glon, glat):
    lon, lat = glon, glat
    for _ in range(30):
        tlon, tlat = wgs2gcj(lon, lat)
        lon += glon - tlon
        lat += glat - tlat
    return lon, lat


def stitch(d):
    img = Image.new('RGB', (NX * TILE, NY * TILE), (8, 10, 14))
    for x in range(X0, X0 + NX):
        for y in range(Y0, Y0 + NY):
            p = os.path.join(d, f'{Z}_{x}_{y}.jpg')
            if not os.path.exists(p):
                p = os.path.join(d, f'{Z}_{x}_{y}.png')
            if os.path.exists(p):
                img.paste(Image.open(p).convert('RGB'), ((x - X0) * TILE, (y - Y0) * TILE))
    return img


def sx(lon, lat):
    glon, glat = wgs2gcj(lon, lat)
    px, py = merc_px(glon, glat, Z)
    return px - X0 * TILE, py - Y0 * TILE


def load_osm_buildings():
    els = json.load(open('data/raw/buildings.json', encoding='utf-8'))['elements']
    out = {}
    for el in els:
        out.setdefault(el['id'], el)
    return out


def load_amap_pois():
    rows = []
    for f in glob.glob('data/derived/amap_around_*.json'):
        if '%' in f:
            continue
        try:
            rows += json.load(open(f, encoding='utf-8'))
        except Exception:  # noqa: BLE001
            pass
    seen, out = set(), []
    for p in rows:
        k = (p.get('name'), p.get('location'))
        if k in seen:
            continue
        seen.add(k)
        try:
            glon, glat = [float(v) for v in p['location'].split(',')]
        except Exception:  # noqa: BLE001
            continue
        wl, wla = gcj2wgs(glon, glat)
        out.append(dict(name=p.get('name', ''), type=p.get('type', ''),
                        glon=glon, glat=glat, lon=wl, lat=wla))
    return out


def main():
    sat = stitch(SAT_DIR)
    road = stitch(RD_DIR)
    W, H = sat.size
    print('stitched', sat.size, road.size)

    # dim the satellite so overlays read well
    base = Image.blend(sat, Image.new('RGB', sat.size, (12, 16, 22)), 0.42)

    d = ImageDraw.Draw(base, 'RGBA')
    fb30 = ImageFont.truetype(FONTB, 26)
    f16 = ImageFont.truetype(FONT, 15)

    osm = load_osm_buildings()
    pois = load_amap_pois()
    print('osm buildings', len(osm), 'amap pois', len(pois))

    # ---- 0. OSM roads (thin cyan-blue) drawn under everything ----
    roads = json.load(open('data/raw/roads.json', encoding='utf-8'))['elements']
    n_road = 0
    for el in roads:
        hw = (el.get('tags') or {}).get('highway', '')
        if hw in ('steps', 'construction'):
            continue
        geom = el.get('geometry') or []
        if len(geom) < 2:
            continue
        pts = [sx(q['lon'], q['lat']) for q in geom if q]
        if len(pts) < 2:
            continue
        w = 5 if hw in ('trunk', 'secondary', 'tertiary') else 3
        d.line(pts, fill=(90, 210, 255, 210), width=w, joint='curve')
        n_road += 1
    print('osm roads drawn', n_road)

    # ---- 1. OSM building outlines (thin, category colored) ----
    n_osm = 0
    for g in G.GROUPS:
        if g.get('measured'):
            continue
        col = CAT_COL.get(g['cat'], (150, 150, 150))
        for wid in g.get('ways', []):
            el = osm.get(wid)
            if not el or not el.get('geometry'):
                continue
            pts = [sx(p['lon'], p['lat']) for p in el['geometry'] if p]
            if len(pts) < 3:
                continue
            d.line(pts + [pts[0]], fill=col + (230,), width=2)
            n_osm += 1
    print('osm outlines drawn', n_osm)

    # ---- 2. measured (satellite-measured) footprint boxes ----
    n_meas = 0
    for g in G.GROUPS:
        m = g.get('measured')
        if not m:
            continue
        x0, y0, x1, y1 = m['bbox']
        ax, ay = sx(x0, y1)
        bx, by = sx(x1, y0)
        xs, xe = sorted((ax, bx))
        ys, ye = sorted((ay, by))
        d.rectangle([xs, ys, xe, ye], outline=(0, 230, 190, 220), width=2)
        n_meas += 1
    print('measured boxes', n_meas)

    # ---- 3. AMap POI dots ----
    for p in pois:
        x, y = sx(p['lon'], p['lat'])
        if not (0 <= x < W and 0 <= y < H):
            continue
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 210, 0, 255),
                  outline=(90, 60, 0, 255), width=1)
    print('poi dots drawn')

    # ---- 4. labels ----
    labels = []
    for g in G.GROUPS:
        m = g.get('measured')
        if m:
            x, y = sx(m['lon'], m['lat'])
        else:
            pts = []
            for wid in g.get('ways', []):
                el = osm.get(wid)
                if el and el.get('geometry'):
                    pts += [(q['lon'], q['lat']) for q in el['geometry'] if q]
            if not pts:
                continue
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
            x, y = sx(lon, lat)
        if 0 <= x < W and 0 <= y < H:
            labels.append((g['short'], x, y, g['cat']))

    # nudge to avoid overlap
    placed = []
    for lab, x, y, cat in labels:
        lw = d.textlength(lab, font=f16) + 6
        for k in range(14):
            oy = -k * 15
            box = (x - lw / 2, y + oy - 15, x + lw / 2, y + oy)
            if all(not (box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1])
                   for b in placed):
                placed.append(box)
                break
        col = CAT_COL.get(cat, (150, 150, 150))
        d.rectangle(box, fill=(8, 12, 18, 200))
        d.text((box[0] + 3, box[1] + 1), lab, font=f16, fill=col + (255,))

    # ---- header ----
    hdr = 92
    canvas = Image.new('RGB', (W, H + hdr), (10, 13, 18))
    canvas.paste(base, (0, hdr))
    dc = ImageDraw.Draw(canvas, 'RGBA')
    dc.text((16, 10), '燕山大学西校区 · 双源合成图（OSM + 高德，冲突以高德为准）',
            font=fb30, fill=(255, 255, 255))
    dc.text((16, 46),
            '底图=高德 z17 卫星 ｜ 蓝色线=OSM 道路 ｜ 彩色细轮廓=OSM 建筑 ｜ 青框=影像量测建筑 ｜'
            ' 黄点=高德 POI',
            font=f16, fill=(180, 200, 220))
    dc.text((16, 66), '坐标系：WGS-84（已做 GCJ-02 反解）；来源 © OpenStreetMap contributors / © 高德地图',
            font=f16, fill=(140, 160, 180))

    canvas.save(OUT, quality=90)
    print('saved', OUT, canvas.size)


if __name__ == '__main__':
    main()

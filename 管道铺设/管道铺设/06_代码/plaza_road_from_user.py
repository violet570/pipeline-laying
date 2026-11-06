"""Turn the user's hand-drawn plaza road (black lines on the screenshot) into
WGS-84 polyline vertices.

The user marked the ring road around the circular plaza. We read the vertices in
screenshot pixel coordinates (712x355 preview = a downscale of the 1600x972 crop
of docs/fig/fig_two_source_campus.jpg), then map them back through:
    preview px -> crop px -> full-figure px -> GCJ-02 web-mercator px -> lon/lat
and finally invert GCJ-02 to WGS-84.

usage: python scripts/plaza_road_from_user.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# --- geometry of the figure the user annotated -------------------------------
Z = 17
TILE = 256
X0, Y0 = 109046, 49659          # top-left tile of the z17 mosaic
FIG_HDR = 92                    # header bar height in fig_two_source_campus.jpg
CROP_BOX = (1000, 92, 2000, 700)
CROP_UP = (1600, 972)
PREVIEW = (712, 355)


def merc_px(lon, lat, z=Z):
    n = 2.0 ** z * TILE
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def px2merc(X, Y):
    return X0 * TILE + X, Y0 * TILE + Y


def merc2lonlat(mx, my, z=Z):
    n = 2.0 ** z * TILE
    lon = mx / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * my / n))))
    return lon, lat


def gcj2wgs(glon, glat):
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

    dlat, dlon = tlat(glon - 105.0, glat - 35.0), tlon(glon - 105.0, glat - 35.0)
    rad = math.radians(glat)
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return glon - dlon, glat - dlat


def preview_to_wgs(px, py):
    """712x355 preview coordinates -> WGS-84 (lon, lat)."""
    # preview -> crop
    cx = px * CROP_UP[0] / PREVIEW[0]
    cy = py * CROP_UP[1] / PREVIEW[1]
    # crop -> full figure
    fx = CROP_BOX[0] + cx
    fy = CROP_BOX[1] + cy - FIG_HDR
    # figure -> mosaic px -> mercator px
    mx, my = px2merc(fx, fy)
    glon, glat = merc2lonlat(mx, my)
    return gcj2wgs(glon, glat)


# Hand-traced vertices from the user's marked screenshot (712x355 px).
# The black strokes trace: the ring road around the circular plaza, a west spur
# down to the lakeside road, an east spur to the service road on the east side,
# and a north link to the through road above the plaza.
# The triangle-marked area on the west is a PARKING LOT, not a road.
ROADS = [
    # ring around the plaza — west flank going north, then over the top,
    # then down the east flank, then back west along the south edge
    ('plaza_ring', [
        (318, 296), (330, 258), (352, 214), (382, 172), (418, 138),
        (462, 118), (505, 108), (536, 108),
    ]),
    ('plaza_ring_e', [
        (536, 108), (556, 128), (566, 160), (568, 196), (558, 232), (536, 262),
        (500, 286), (458, 300), (416, 306), (378, 306), (348, 302), (318, 296),
    ]),
    # west spur: from the ring's southwest corner out to the lake-side road
    ('plaza_west_spur', [
        (318, 296), (300, 286), (282, 268), (268, 244), (258, 218),
    ]),
    # north link: from the ring's north point up to the arterial road
    ('plaza_north_link', [
        (505, 108), (494, 88), (486, 62), (480, 38), (476, 14),
    ]),
    # east spur: from the ring's east side out to the eastern service road
    ('plaza_east_spur', [
        (558, 232), (586, 236), (618, 244), (652, 254), (690, 262),
    ]),
]


def main():
    out = {}
    for name, pts in ROADS:
        conv = [preview_to_wgs(x, y) for x, y in pts]
        out[name] = [[round(lon, 6), round(lat, 6)] for lon, lat in conv]
        print(f'{name}: {len(conv)} pts')
        for lon, lat in conv:
            print(f'   {lat:.6f}, {lon:.6f}')

    os.makedirs('data/derived', exist_ok=True)
    p = 'data/derived/plaza_roads_user.json'
    json.dump({'note': 'hand-traced by the user on docs/fig/fig_two_source_campus.jpg; '
                       'the triangle-marked area is a parking lot, not a road',
               'segments': out}, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('->', p)


if __name__ == '__main__':
    main()

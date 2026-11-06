"""Define the plaza ring road directly in FULL-FIGURE pixel space.

This avoids every preview/crop conversion. The reference frame is
docs/fig/fig_two_source_campus.jpg (2816 x 2652, header bar 92 px on top).
Pixel -> WGS-84 uses the same inverse as scripts/fig_two_source.py's sx().

Calibration anchors (measured building centres, full-figure px):
    X01 信息学院   (1654.7, 221.2)  -> 119.515542, 39.917205
    X02 人工智能   (1603.5, 335.5)  -> 119.514990, 39.916263
    X03 理学院     (1727.3, 342.9)  -> 119.516324, 39.916206

The plaza ring that encloses those three buildings is centred near
(1665, 300) with a radius of about 72 px.

usage: python scripts/plaza_road_trace.py
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

Z = 17
TILE = 256
X0, Y0 = 109046, 49659
FIG_HDR = 92


def merc2lonlat(mx, my, z=Z):
    n = 2.0 ** z * TILE
    return mx / n * 360.0 - 180.0, math.degrees(
        math.atan(math.sinh(math.pi * (1 - 2 * my / n))))


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


def figpx_to_wgs(fx, fy):
    """Full-figure pixel (including the 92 px header) -> WGS-84 lon/lat."""
    mx = X0 * TILE + fx
    my = Y0 * TILE + (fy - FIG_HDR)
    glon, glat = merc2lonlat(mx, my)
    return gcj2wgs(glon, glat)


# --------------------------------------------------------------- traced roads
CX, CY, R = 1665.0, 300.0, 72.0


def ring_pts(a0, a1, n):
    return [(CX + R * math.cos(math.radians(a)), CY + R * math.sin(math.radians(a)))
            for a in [a0 + (a1 - a0) * i / (n - 1) for i in range(n)]]


ROADS = {
    # closed ring around the plaza
    'plaza_ring': ring_pts(-90.0, 270.0, 25),
    # west approach -> toward the road junction west of the plaza
    'plaza_west_approach': [
        (CX - R, CY), (1560, 302), (1520, 306), (1480, 312), (1442, 320), (1408, 330),
    ],
    # north link -> up to the through road above the plaza
    'plaza_north_link': [
        (CX, CY - R), (1668, 210), (1670, 190), (1672, 170), (1674, 150),
    ],
    # east spur -> out to the eastern service road
    'plaza_east_spur': [
        (CX + R, CY), (1755, 302), (1790, 308), (1826, 316), (1862, 324), (1898, 332),
    ],
    # south spur -> down toward the buildings south of the plaza
    'plaza_south_spur': [
        (CX, CY + R), (1665, 388), (1665, 414), (1665, 440), (1665, 466),
    ],
}


def main():
    out = {}
    for name, pts in ROADS.items():
        conv = [figpx_to_wgs(x, y) for x, y in pts]
        out[name] = [[lon, lat] for lon, lat in conv]

    data = {
        'note': ('hand-defined in full-figure pixel space of '
                 'docs/fig/fig_two_source_campus.jpg, calibrated on the three '
                 'measured colleges; the triangle-marked area is a parking lot'),
        'frame': 'full-figure px, 2816x2652, header 92',
        'segments': out,
    }
    json.dump(data, open('data/derived/plaza_roads_user.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(f'{k}: {len(v)} pts  '
              f'[{v[0][0]:.6f},{v[0][1]:.6f}] -> [{v[-1][0]:.6f},{v[-1][1]:.6f}]')
    print('-> data/derived/plaza_roads_user.json')


if __name__ == '__main__':
    main()

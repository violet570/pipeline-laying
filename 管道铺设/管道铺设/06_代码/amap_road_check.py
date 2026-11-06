"""Check whether AMap has road network inside the circle plaza by sampling.

Two independent probes:
  1) place/around with kw=停车场 / 出入口 / 门  -> parking lots imply roads
  2) regeo (逆地理编码) on a dense grid -> returns nearest road name+dir per point,
     which is AMap's own "what road is here" answer. Empty text = no road nearby.
usage: python scripts/amap_road_check.py
"""
import json
import math
import time
import urllib.parse
import urllib.request

KEY = 'ed947ef3bd8ceef0f7a10b8741102dec'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36'}


def get(path, **params):
    params['key'] = KEY
    params.setdefault('output', 'JSON')
    url = 'https://restapi.amap.com/v3/' + path + '?' + urllib.parse.urlencode(params)
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(0.6)
    print('GET FAIL', path, last)
    return {}


def wgs2gcj(lon, lat):
    """WGS-84 -> GCJ-02 (standard algorithm)."""
    a = 6378245.0
    ee = 0.00669342162296594323

    def tlat(x, y):
        r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
             + 0.2 * math.sqrt(abs(x)))
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

    dlat = tlat(lon - 105.0, lat - 35.0)
    dlon = tlon(lon - 105.0, lat - 35.0)
    rad = lat / 180.0 * math.pi
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def regeo_road(lon_g, lat_g):
    j = get('geocode/regeo', location=f'{lon_g:.6f},{lat_g:.6f}', extensions='base')
    if j.get('status') != '1':
        return None
    rc = j.get('regeocode') or {}
    roads = rc.get('roads') or []
    return [(r.get('name') or '', r.get('distance') or '', r.get('direction') or '')
            for r in roads]


def main():
    # plaza bbox in WGS-84 (from the registry X01-X03 measurements)
    s, w, n, e = 39.9150, 119.5135, 39.9186, 119.5178
    nx, ny = 9, 9
    print(f'== regeo grid {nx}x{ny} over plaza WGS bbox {s},{w},{n},{e} ==')
    hits = 0
    road_names = {}
    for iy in range(ny):
        for ix in range(nx):
            lat = s + (n - s) * iy / (ny - 1)
            lon = w + (e - w) * ix / (nx - 1)
            glon, glat = wgs2gcj(lon, lat)
            rs = regeo_road(glon, glat)
            if rs:
                hits += 1
                for nm, dist, _d in rs:
                    if nm:
                        road_names[nm] = road_names.get(nm, 0) + 1
            time.sleep(0.09)
    print(f'points with >=1 road: {hits}/{nx * ny}')
    for nm, c in sorted(road_names.items(), key=lambda x: -x[1]):
        print(f'  {nm}\t{c}')

    # parking / gates around the plaza — strongest proxy for internal roads
    print('\n== place/around kw=停车场 radius 700 ==')
    glon, glat = wgs2gcj((w + e) / 2, (s + n) / 2)
    for kw in ('停车场', '门'):
        j = get('place/around', location=f'{glon:.6f},{glat:.6f}', radius=700,
                offset=25, page=1, keywords=kw, extensions='base')
        pois = j.get('pois') or []
        print(f'-- {kw}: count={j.get("count")}')
        for p in pois:
            print(f'   {p.get("name")}\t{p.get("location")}\t{p.get("type")}')
        time.sleep(0.2)


if __name__ == '__main__':
    main()

/**
 * Probe AMap for road geometry inside the campus via the
 * 矢量底图 v3 rastertile endpoint (tile, not POI).
 * Also probes the JS-API style "mapapi" tile server which serves road+label tiles.
 * usage: node scripts/amap_roadtile_check.js
 */
const fs = require('fs');
const path = require('path');

const UA = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  Referer: 'https://www.amap.com/',
};

const Z = 18;
const N = 2 ** Z * 256;

function px(lon, lat) {
  const x = (lon + 180) / 360 * N;
  const s = Math.sin(lat * Math.PI / 180);
  const y = (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * N;
  return { x, y };
}

function tileRange(s, w, n, e) {
  const a = px(w, n), b = px(e, s);
  return {
    x0: Math.floor(a.x / 256), x1: Math.floor(b.x / 256),
    y0: Math.floor(a.y / 256), y1: Math.floor(b.y / 256),
  };
}

const MIRRORS = ['webst01', 'webst02', 'webrd01', 'webrd02'];
const STYLES = [
  ['webrd', 'style=8&lang=zh_cn&size=1&scale=1'],
  ['webst', 'style=6'],
];

async function grab(host, qs, x, y, out) {
  const url = `https://${host}.is.autonavi.com/appmaptile?${qs}&x=${x}&y=${y}&z=${Z}`;
  const r = await fetch(url, { headers: UA });
  if (!r.ok) return { ok: false, status: r.status };
  const buf = Buffer.from(await r.arrayBuffer());
  fs.writeFileSync(out, buf);
  return { ok: true, bytes: buf.length, ct: r.headers.get('content-type') };
}

(async () => {
  // plaza bbox WGS-84 -> GCJ-02 handled implicitly: AMap tiles are GCJ, so shift input.
  const s = 39.9150, w = 119.5135, n = 39.9186, e = 119.5178;
  const dLon = 0.0049805, dLat = 0.0013812;   // GCJ offset for this area
  const t = tileRange(s + dLat, w + dLon, n + dLat, e + dLon);
  console.log('tiles', JSON.stringify(t));

  const dir = 'data/tiles/amap_plaza_z18';
  fs.mkdirSync(dir, { recursive: true });

  for (const [kind, qs] of STYLES) {
    let ok = 0, fail = 0;
    for (let x = t.x0; x <= t.x1; x++) {
      for (let y = t.y0; y <= t.y1; y++) {
        const out = path.join(dir, `${kind}_${x}_${y}.png`);
        const host = kind === 'webrd' ? (x % 2 ? 'webrd01' : 'webrd02') : (x % 2 ? 'webst01' : 'webst02');
        const res = await grab(host, qs, x, y, out);
        if (res.ok && res.bytes > 800) ok++; else { fail++; console.log('fail', kind, x, y, res.status, res.bytes); }
      }
    }
    console.log(kind, 'ok', ok, 'fail', fail, 'tiles', (t.x1 - t.x0 + 1) * (t.y1 - t.y0 + 1));
  }
  console.log('dir', dir);
})();

/* Fetch z17 高德 satellite tiles + OSM overlays for the WHOLE west campus.

Why: the existing z18 mosaic only covers the dorm belt (lon 119.505-119.523).
For a campus-wide inventory (图书馆 / 里仁楼 / 高压中心 / 体育馆 / 艺术楼 ...) we
need z17 tiles covering the full boundary bbox (minlon 119.5061, maxlon 119.5309,
minlat 39.9027, maxlat 39.9188).

Outputs
  data/tiles/campus_sat_z17_full/z_x_y.jpg
  data/tiles/campus_road_z17_full/z_x_y.png
  data/raw/campus_overlay_z17.json   {buildings, roads, areas, water, pitch, groups}

Run: node scripts/fetch_campus_z17.js
*/
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TILES = path.join(ROOT, 'data', 'tiles');

// campus bbox (WGS-84) + margin
const BB = { minLon: 119.5045, maxLon: 119.5325, minLat: 39.9010, maxLat: 39.9199 };
// z18 needs a slightly wider window: the library sits near the east edge and its
// GCJ-02-shifted footprint (≈ +511 m east) falls outside the z17-derived bbox.
const BB18 = { minLon: 119.5045, maxLon: 119.5385, minLat: 39.9010, maxLat: 39.9215 };

function lon2x(lon, z) { return (lon + 180) / 360 * Math.pow(2, z); }
function lat2y(lat, z) {
  const s = Math.sin(lat * Math.PI / 180);
  return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * Math.pow(2, z);
}

const JOBS = [
  { name: 'campus_sat_z17_full', z: 17, url: (z, x, y) => `https://webst01.is.autonavi.com/appmaptile?style=6&x=${x}&y=${y}&z=${z}`, ext: 'jpg', ref: 'https://www.amap.com/' },
  { name: 'campus_road_z17_full', z: 17, url: (z, x, y) => `https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x=${x}&y=${y}&z=${z}`, ext: 'png', ref: 'https://www.amap.com/' },
  // z18 (0.46 m/px) over the whole campus: needed for the registration audit panels,
  // where a 0.92 m/px z17 base is too coarse to judge roof-edge alignment.
  { name: 'campus_sat_z18_full', z: 18, bb: BB18, url: (z, x, y) => `https://webst01.is.autonavi.com/appmaptile?style=6&x=${x}&y=${y}&z=${z}`, ext: 'jpg', ref: 'https://www.amap.com/' },
];

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

async function fetchTile(url, ref, tries = 4) {
  let lastErr;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA, 'Referer': ref, 'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8' } });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const buf = Buffer.from(await r.arrayBuffer());
      if (buf.length < 500) throw new Error('too small ' + buf.length);
      return buf;
    } catch (e) {
      lastErr = e;
      await new Promise(res => setTimeout(res, 260 * (i + 1)));
    }
  }
  throw lastErr;
}

async function runJob(job) {
  const dir = path.join(TILES, job.name);
  fs.mkdirSync(dir, { recursive: true });
  const z = job.z;
  const bb = job.bb || BB;
  const x0 = Math.floor(lon2x(bb.minLon, z));
  const x1 = Math.floor(lon2x(bb.maxLon, z));
  const y0 = Math.floor(lat2y(bb.maxLat, z));
  const y1 = Math.floor(lat2y(bb.minLat, z));
  let ok = 0, fail = 0, skip = 0;
  const tasks = [];
  for (let x = x0; x <= x1; x++) {
    for (let y = y0; y <= y1; y++) {
      const fp = path.join(dir, `${z}_${x}_${y}.${job.ext}`);
      if (fs.existsSync(fp) && fs.statSync(fp).size > 500) { skip++; continue; }
      tasks.push({ x, y, fp });
    }
  }
  const CONC = 6;
  let idx = 0;
  async function worker() {
    while (idx < tasks.length) {
      const t = tasks[idx++];
      try {
        const buf = await fetchTile(job.url(z, t.x, t.y), job.ref);
        fs.writeFileSync(t.fp, buf);
        ok++;
      } catch (e) {
        fail++;
        if (fail < 6) console.error('fail', t.x, t.y, e.message);
      }
    }
  }
  await Promise.all(Array.from({ length: CONC }, worker));
  console.log(`${job.name}: z${z} x=${x0}..${x1} y=${y0}..${y1} ok=${ok} skip=${skip} fail=${fail}`);
}

(async () => {
  for (const job of JOBS) await runJob(job);
  console.log('done');
})();

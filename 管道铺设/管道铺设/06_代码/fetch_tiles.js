// Fetch raster map tiles for Yanshan University West Campus from sources reachable here.
// Sources: AMap road (GCJ-02), AMap satellite (GCJ-02), Esri World Imagery (WGS-84)
// Saves tiles as data/tiles/<source>/<z>_<x>_<y>.(png|jpg)
const fs = require('fs');
const path = require('path');

const OUT_ROOT = path.join(__dirname, '..', 'data', 'tiles');

function lon2tile(lon, z) { return Math.floor(((lon + 180) / 360) * Math.pow(2, z)); }
function lat2tile(lat, z) {
  const rad = (lat * Math.PI) / 180;
  return Math.floor(((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * Math.pow(2, z));
}

const SOURCES = {
  amap_road: {
    url: (x, y, z) => `https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x=${x}&y=${y}&z=${z}`,
    ext: 'png', headers: { 'Referer': 'https://ditu.amap.com/' },
  },
  amap_sat: {
    url: (x, y, z) => `https://webst01.is.autonavi.com/appmaptile?style=6&x=${x}&y=${y}&z=${z}`,
    ext: 'jpg', headers: { 'Referer': 'https://ditu.amap.com/' },
  },
  esri_sat: {
    url: (x, y, z) => `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`,
    ext: 'jpg', headers: { 'Referer': 'https://www.arcgis.com/' },
  },
};

// name, source, zoom, bbox [west, south, east, north]
const JOBS = [
  { name: 'campus_road_z17', source: 'amap_road', z: 17, bbox: [119.5010, 39.8985, 119.5370, 39.9230] },
  { name: 'campus_sat_z17', source: 'amap_sat', z: 17, bbox: [119.5010, 39.8985, 119.5370, 39.9230] },
  { name: 'campus_esri_z17', source: 'esri_sat', z: 17, bbox: [119.5010, 39.8985, 119.5370, 39.9230] },
  { name: 'dorms_road_z18', source: 'amap_road', z: 18, bbox: [119.5050, 39.9015, 119.5320, 39.9210] },
  { name: 'dorms_sat_z18', source: 'amap_sat', z: 18, bbox: [119.5050, 39.9015, 119.5320, 39.9210] },
];

async function fetchTile(url, headers, attempt = 1) {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36', ...headers }, signal: AbortSignal.timeout(20000) });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return Buffer.from(await res.arrayBuffer());
}

(async () => {
  for (const job of JOBS) {
    const [w, s, e, n] = job.bbox;
    const x0 = lon2tile(w, job.z), x1 = lon2tile(e, job.z);
    const y0 = lat2tile(n, job.z), y1 = lat2tile(s, job.z);
    const nx = x1 - x0 + 1, ny = y1 - y0 + 1;
    const dir = path.join(OUT_ROOT, job.name);
    fs.mkdirSync(dir, { recursive: true });
    const src = SOURCES[job.source];
    console.log(`== ${job.name}: ${nx}x${ny}=${nx * ny} tiles, x ${x0}-${x1}, y ${y0}-${y1}, z${job.z}`);
    let ok = 0, fail = 0;
    const t0 = Date.now();
    // small concurrency pool
    const tasks = [];
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) tasks.push([x, y]);
    let idx = 0;
    async function worker() {
      while (idx < tasks.length) {
        const [x, y] = tasks[idx++];
        const file = path.join(dir, `${job.z}_${x}_${y}.${src.ext}`);
        if (fs.existsSync(file) && fs.statSync(file).size > 100) { ok++; continue; }
        for (let a = 1; a <= 3; a++) {
          try {
            const buf = await fetchTile(src.url(x, y, job.z), src.headers);
            fs.writeFileSync(file, buf); ok++; break;
          } catch (err) {
            if (a === 3) { fail++; console.log(`  tile ${x},${y} failed: ${err.message}`); }
            else await new Promise(r => setTimeout(r, 500 * a));
          }
        }
      }
    }
    await Promise.all(Array.from({ length: 8 }, worker));
    console.log(`== ${job.name}: ok=${ok} fail=${fail} ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  }
  console.log('DONE');
})();

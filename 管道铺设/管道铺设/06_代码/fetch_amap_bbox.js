/* Fetch AMap raster tiles (satellite / road+labels) for a bbox and stitch them.
 *
 * usage: node scripts/fetch_amap_bbox.js <job> <style> <z> <minLon> <minLat> <maxLon> <maxLat>
 *   style 6 = 卫星影像, 7 = 路网, 8 = 路网+中文注记
 */
const fs = require('fs');
const path = require('path');

const [, , job, styleArg, zArg, minLonA, minLatA, maxLonA, maxLatA] = process.argv;
if (!job) {
  console.error('usage: node scripts/fetch_amap_bbox.js <job> <style> <z> <minLon> <minLat> <maxLon> <maxLat>');
  process.exit(1);
}
const style = Number(styleArg || 8);
const z = Number(zArg || 18);
const minLon = Number(minLonA);
const minLat = Number(minLatA);
const maxLon = Number(maxLonA);
const maxLat = Number(maxLatA);

const ROOT = path.resolve(__dirname, '..');
const DIR = path.join(ROOT, 'data', 'tiles', job);

function lon2x(lon, zz) { return Math.floor((lon + 180) / 360 * Math.pow(2, zz)); }
function lat2y(lat, zz) {
  const r = lat * Math.PI / 180;
  return Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * Math.pow(2, zz));
}

const x0 = lon2x(minLon, z), x1 = lon2x(maxLon, z);
const y0 = lat2y(maxLat, z), y1 = lat2y(minLat, z);
console.log('tiles x', x0, x1, 'y', y0, y1, '=', (x1 - x0 + 1) * (y1 - y0 + 1));

fs.mkdirSync(DIR, { recursive: true });

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  'Referer': 'https://www.amap.com/',
};

async function grab(x, y) {
  const f = path.join(DIR, `${z}_${x}_${y}.png`);
  if (fs.existsSync(f) && fs.statSync(f).size > 1000) return 'skip';
  const hosts = style === 6
    ? ['webst01', 'webst02', 'webst03', 'webst04']
    : ['webrd01', 'webrd02', 'webrd03', 'webrd04'];
  for (let k = 0; k < 8; k++) {
    const h = hosts[k % hosts.length];
    const url = `https://${h}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1`
      + `&style=${style}&x=${x}&y=${y}&z=${z}`;
    try {
      const r = await fetch(url, { headers: HEADERS });
      if (r.ok) {
        const b = Buffer.from(await r.arrayBuffer());
        if (b.length > 500) { fs.writeFileSync(f, b); return 'ok'; }
      }
    } catch (e) { /* retry */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  return 'fail';
}

(async () => {
  let ok = 0, skip = 0, fail = 0;
  const jobs = [];
  for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) jobs.push([x, y]);
  for (let i = 0; i < jobs.length; i += 8) {
    const batch = jobs.slice(i, i + 8);
    const res = await Promise.all(batch.map(([x, y]) => grab(x, y)));
    for (const r of res) { if (r === 'ok') ok++; else if (r === 'skip') skip++; else fail++; }
  }
  console.log('ok', ok, 'skip', skip, 'fail', fail, '->', DIR);
})();

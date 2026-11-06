/* Fetch FULL building geometry for the west-campus bounding box, at the wider extent used
 * by verify_2026 (which only had centres).  Output: data/raw/buildings_full.json
 *
 * Why: the first fetch (buildings.json, 102 ways) used a bbox clipped to the campus polygon
 * and therefore missed 201 buildings that OSM really has — including 燕大西校区大食堂,
 * 里仁实验楼, 图文信息楼, 材料A楼, 燕大西区浴池.  This run takes the whole west-campus
 * rectangle so nothing is silently dropped.
 *
 * Run: node scripts/fetch_full_buildings.js
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const ENDPOINTS = [
  'https://overpass.openstreetmap.fr/api/interpreter',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
];
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

function post(ep, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(ep);
    const req = https.request({
      hostname: u.hostname, path: u.pathname, method: 'POST',
      headers: {
        'User-Agent': UA, 'Referer': 'https://overpass-turbo.eu/',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body),
      },
      timeout: 180000,
    }, (res) => {
      let buf = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { buf += c; });
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode + ' ' + buf.slice(0, 300)));
        try { resolve(JSON.parse(buf)); } catch (e) { reject(new Error('bad json: ' + buf.slice(0, 200))); }
      });
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function run(q) {
  const body = 'data=' + encodeURIComponent(q);
  let last;
  for (let i = 0; i < 5; i++) {
    const ep = ENDPOINTS[i % ENDPOINTS.length];
    try {
      console.log('  try', i + 1, ep);
      return await post(ep, body);
    } catch (e) {
      last = e;
      console.error('  fail:', e.message);
    }
  }
  throw last;
}

// West-campus rectangle, generous enough to include the whole 里仁 campus + ring roads,
// but NOT the east campus (which starts around lon 119.527 at lat 39.90, but they overlap
// in latitude, so we keep east bound at 119.5275 and clip by the polygon later).
const BBOX = '39.8980,119.4980,39.9240,119.5275';

const QUERY = `[out:json][timeout:180];
(
  way["building"](${BBOX});
  relation["building"](${BBOX});
);
out geom tags;`;

(async () => {
  console.log('querying', BBOX);
  const r = await run(QUERY);
  const els = r.elements || [];
  const withGeom = els.filter((e) => (e.geometry && e.geometry.length >= 3) ||
                                     (e.members && e.members.length));
  const out = {
    fetched_at: new Date().toISOString(),
    bbox: BBOX,
    osm_timestamp: (r.osm3s || {}).timestamp_osm_base || null,
    generator: 'scripts/fetch_full_buildings.js',
    elements: withGeom,
  };
  const p = path.join(__dirname, '..', 'data', 'raw', 'buildings_full.json');
  fs.writeFileSync(p, JSON.stringify(out), 'utf8');
  console.log('elements:', els.length, 'withGeometry:', withGeom.length, '->', p);
  const named = withGeom.filter((e) => e.tags && e.tags.name).length;
  console.log('named:', named);
})();

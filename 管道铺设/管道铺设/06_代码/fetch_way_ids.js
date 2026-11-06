/* Fetch a fixed list of OSM way ids WITH geometry, whatever their bbox.
 * Used to pull the buildings that verify_2026 found by centre but whose geometry the
 * rectangle query does not return (they sit in ways clipped by the point-in-polygon step
 * or are drawn as outer rings of relations).
 *
 * Run: node scripts/fetch_way_ids.js
 * Out: data/raw/buildings_extra.json
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const ENDPOINTS = [
  'https://overpass.openstreetmap.fr/api/interpreter',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
];

// ids the user called out + everything named in verify_2026 that has no geometry yet
const IDS = [9676180, 9473739, 9473738, 9680716, 9676079];

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
      timeout: 120000,
    }, (res) => {
      let b = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { b += c; });
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode + ' ' + b.slice(0, 200)));
        try { resolve(JSON.parse(b)); } catch (e) { reject(new Error('bad json')); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.write(body);
    req.end();
  });
}

(async () => {
  const q = `[out:json][timeout:90];(way(id:${IDS.join(',')});relation(id:${IDS.join(',')}););out geom tags;`;
  let r;
  for (let i = 0; i < 5; i++) {
    try {
      r = await post(ENDPOINTS[i % ENDPOINTS.length], 'data=' + encodeURIComponent(q));
      break;
    } catch (e) {
      console.error('  fail', i + 1, e.message);
    }
  }
  if (!r) throw new Error('all endpoints failed');
  const els = (r.elements || []).filter((e) => (e.geometry || []).length >= 3 || (e.members || []).length);
  console.log('returned', (r.elements || []).length, 'usable', els.length);
  for (const e of els) console.log(' ', e.type, e.id, JSON.stringify(e.tags).slice(0, 110));
  const p = path.join(__dirname, '..', 'data', 'raw', 'buildings_extra.json');
  fs.writeFileSync(p, JSON.stringify({
    fetched_at: new Date().toISOString(),
    osm_timestamp: (r.osm3s || {}).timestamp_osm_base || null,
    generator: 'scripts/fetch_way_ids.js',
    ids: IDS,
    elements: els,
  }), 'utf8');
  console.log('->', p);
})();

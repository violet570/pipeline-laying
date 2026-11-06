/* Validate every candidate way id from verify_2026 by asking Overpass for the way BY ID and
 * checking that its actual coordinates fall inside the west-campus box.
 *
 * This catches the failure mode found on 2026-10-28: verify_2026.json carried 201 building
 * records whose ids actually resolve to North-Dakota roads, i.e. the ids were not bound to
 * the campus geometry.  Only ids whose geometry really lands in Qinhuangdao survive.
 *
 * Run: node scripts/validate_ids.js        (writes data/derived/id_validation.json)
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const EPS = [
  'https://overpass.openstreetmap.fr/api/interpreter',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
];
let EP = EPS[0];

const BOX = { s: 39.890, w: 119.490, n: 39.930, e: 119.550 };

function post(body) {
  return new Promise((resolve, reject) => {
    const u = new URL(EP);
    const req = https.request({
      hostname: u.hostname, path: u.pathname, method: 'POST',
      headers: {
        'User-Agent': UA, 'Referer': 'https://overpass-turbo.eu/',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body),
      },
      timeout: 180000,
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

async function retry(q) {
  let last;
  for (let i = 0; i < 8; i++) {
    EP = EPS[i % EPS.length];
    try { return await post('data=' + encodeURIComponent(q)); }
    catch (e) { last = e; console.error('   retry', i + 1, e.message.slice(0, 60)); }
  }
  throw last;
}

(async () => {
  const verify = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'raw', 'verify_2026.json'), 'utf8'));
  const base = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'raw', 'buildings.json'), 'utf8'));
  const baseIds = new Set(base.elements.map((e) => e.id));
  const cand = verify.buildings.filter((e) => !baseIds.has(e.id)).map((e) => e.id);
  console.log('candidate ids to validate:', cand.length);

  const results = [];
  const CHUNK = 15;
  for (let i = 0; i < cand.length; i += CHUNK) {
    const part = cand.slice(i, i + CHUNK);
    const q = `[out:json][timeout:120];way(id:${part.join(',')});out geom tags;`;
    const r = await retry(q);
    const got = new Map(r.elements.map((e) => [e.id, e]));
    for (const id of part) {
      const e = got.get(id);
      if (!e) { results.push({ id, status: 'missing' }); continue; }
      const g = e.geometry || [];
      if (!g.length) { results.push({ id, status: 'no-geom', tags: e.tags }); continue; }
      const lats = g.map((p) => p.lat), lons = g.map((p) => p.lon);
      const cen = {
        lat: lats.reduce((a, b) => a + b, 0) / lats.length,
        lon: lons.reduce((a, b) => a + b, 0) / lons.length,
      };
      const inside = cen.lat >= BOX.s && cen.lat <= BOX.n && cen.lon >= BOX.w && cen.lon <= BOX.e;
      results.push({
        id, status: inside ? 'ok' : 'OUT_OF_AREA',
        lat: +cen.lat.toFixed(6), lon: +cen.lon.toFixed(6),
        name: (e.tags && e.tags.name) || null,
        building: (e.tags && e.tags.building) || null,
        levels: (e.tags && e.tags['building:levels']) || null,
        npts: g.length,
      });
    }
    console.log('  checked', Math.min(i + CHUNK, cand.length), '/', cand.length);
  }

  const ok = results.filter((r) => r.status === 'ok');
  const bad = results.filter((r) => r.status !== 'ok');
  console.log('\nVALID (inside campus box):', ok.length);
  console.log('INVALID:', bad.length);
  for (const b of bad.slice(0, 15)) console.log('  ', b.id, b.status, b.lat, b.lon, b.name);
  const out = path.join(__dirname, '..', 'data', 'derived', 'id_validation.json');
  fs.writeFileSync(out, JSON.stringify({ checked_at: new Date().toISOString(), box: BOX, ok, bad }, null, 1), 'utf8');
  console.log('->', out);
})();

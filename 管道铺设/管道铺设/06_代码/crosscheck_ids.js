/* Cross-check: query the SAME ids on TWO independent Overpass instances and compare tags.
 * If one instance returns North Dakota roads for these ids, that instance is serving a
 * different/partial planet and must not be trusted for id lookups.
 *
 * Run: node scripts/crosscheck_ids.js
 */
const https = require('https');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const IDS = [9676180, 9473739, 9680716, 9676079, 696280904];

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
      timeout: 90000,
    }, (res) => {
      let b = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { b += c; });
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode + ' ' + b.slice(0, 160)));
        try { resolve(JSON.parse(b)); } catch (e) { reject(new Error('bad json')); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.write(body);
    req.end();
  });
}

const ENDPOINTS = [
  'https://overpass.openstreetmap.fr/api/interpreter',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
];

(async () => {
  const q = `[out:json][timeout:60];way(id:${IDS.join(',')});out geom tags;`;
  for (const ep of ENDPOINTS) {
    try {
      const r = await post(ep, 'data=' + encodeURIComponent(q));
      console.log('\n=== ' + ep);
      console.log('osm3s:', JSON.stringify(r.osm3s || {}));
      for (const e of r.elements) {
        const g = e.geometry || [];
        const cen = g.length ? { lat: g[0].lat.toFixed(5), lon: g[0].lon.toFixed(5) } : null;
        console.log(' ', e.id, (e.tags && e.tags.name) || '(no name)',
                    '| pts', g.length, '| first', JSON.stringify(cen));
      }
    } catch (e) {
      console.log('\n=== ' + ep + '  FAILED: ' + e.message);
    }
  }
})();

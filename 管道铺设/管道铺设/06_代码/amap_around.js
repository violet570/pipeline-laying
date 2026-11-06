/**
 * Enumerate ALL AMap POIs within a radius of a GCJ-02 point (paginated).
 * usage: node scripts/amap_around.js <lonGCJ> <latGCJ> <radius> [keywords] [maxPages]
 */
const fs = require('fs');
const KEY = process.env.AMAP_KEY || 'ed947ef3bd8ceef0f7a10b8741102dec';
const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
};

async function page(lon, lat, radius, kw, p) {
  const url = `https://restapi.amap.com/v3/place/around?key=${KEY}&location=${lon},${lat}`
    + `&radius=${radius}&offset=25&page=${p}&extensions=base&output=JSON`
    + (kw ? `&keywords=${encodeURIComponent(kw)}` : '');
  const r = await fetch(url, { headers: HEADERS });
  const j = JSON.parse(await r.text());
  if (j.status !== '1') {
    console.log('ERR', j.status, j.info, j.infocode);
    return { pois: [], count: 0 };
  }
  return { pois: j.pois || [], count: Number(j.count || 0) };
}

(async () => {
  const [, , lonA, latA, rA, kw = '', mpA] = process.argv;
  const lon = Number(lonA), lat = Number(latA), radius = Number(rA);
  const maxPages = Number(mpA || 20);
  const seen = new Map();
  for (let p = 1; p <= maxPages; p++) {
    const { pois, count } = await page(lon, lat, radius, kw, p);
    if (p === 1) console.log(`count=${count} radius=${radius} kw="${kw}"`);
    if (!pois.length) break;
    for (const q of pois) {
      const k = q.name + '|' + q.location;
      if (!seen.has(k)) seen.set(k, q);
    }
    if (seen.size >= count) break;
    await new Promise((r) => setTimeout(r, 220));
  }
  const rows = [...seen.values()];
  console.log('unique', rows.length);
  rows.sort((a, b) => String(a.name).localeCompare(String(b.name), 'zh'));
  for (const q of rows) {
    console.log(`${q.name}\t${q.location}\t${q.type || ''}\t${q.address || ''}`);
  }
  const out = kw ? 'amap_around_' + kw + '.json' : 'amap_around.json';
  fs.writeFileSync('data/derived/' + out, JSON.stringify(rows, null, 1));
  console.log('-> data/derived/' + out);
})();

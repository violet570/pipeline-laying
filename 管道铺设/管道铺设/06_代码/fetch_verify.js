/* Re-query Overpass for the west campus with a WIDER bbox and more tags, to verify
   the buildings the user corrected:
     - 两个食堂（西区大食堂 vs 燕园餐厅）
     - 信息科学与工程学院 / 人工智能学院(软件学院) / 理学院（北侧圆形广场内 3 栋）
     - 燕山大学机械厂（一教二教旁 4 栋连体）
     - 里仁实验楼（里仁教学楼旁）
     - 第四体育场 / 体育馆（操场旁）
   Also pulls amenity/office/man-made/landuse so we don't miss POI-only records.

   Output: data/raw/verify_2026.json
   Run: node scripts/fetch_verify.js
*/
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'data', 'raw', 'verify_2026.json');

// WIDER than the campus boundary: includes the north 家属区/里仁 ring where OSM data
// for 学院楼 lives, and a margin east/south so nothing on the edge is clipped.
const BB = { south: 39.8980, west: 119.4980, north: 39.9240, east: 119.5400 };

const Q = `
[out:json][timeout:180];
(
  way["building"](${BB.south},${BB.west},${BB.north},${BB.east});
  relation["building"](${BB.south},${BB.west},${BB.north},${BB.east});
);
out tags center;
`;

const Q2 = `
[out:json][timeout:120];
(
  node["amenity"](${BB.south},${BB.west},${BB.north},${BB.east});
  node["office"](${BB.south},${BB.west},${BB.north},${BB.east});
  node["leisure"](${BB.south},${BB.west},${BB.north},${BB.east});
  node["man_made"](${BB.south},${BB.west},${BB.north},${BB.east});
  node["tourism"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["leisure"="pitch"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["leisure"="sports_centre"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["leisure"="stadium"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["landuse"="industrial"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["man_made"="works"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["shop"](${BB.south},${BB.west},${BB.north},${BB.east});
  way["amenity"="restaurant"](${BB.south},${BB.west},${BB.north},${BB.east});
);
out tags center;
`;

const ENDPOINTS = [
  'https://overpass.openstreetmap.fr/api/interpreter',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
];
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

async function overpass(q, tries = 4) {
  let last;
  for (let i = 0; i < tries; i++) {
    const ep = ENDPOINTS[i % ENDPOINTS.length];
    try {
      const r = await fetch(ep, {
        method: 'POST',
        headers: {
          'User-Agent': UA,
          'Referer': 'https://overpass-turbo.eu/',
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'data=' + encodeURIComponent(q),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + ep);
      const j = await r.json();
      return j.elements || [];
    } catch (e) {
      last = e;
      console.error('  retry', i + 1, e.message);
      await new Promise(res => setTimeout(res, 900 * (i + 1)));
    }
  }
  throw last;
}

(async () => {
  console.log('querying buildings in', BB);
  const b = await overpass(Q);
  console.log('  buildings:', b.length);
  console.log('querying POI/pitch/shop');
  const p = await overpass(Q2);
  console.log('  pois/areas:', p.length);

  const out = {
    fetched_at: new Date().toISOString(),
    bbox: BB,
    buildings: b,
    pois: p,
  };
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('->', OUT);

  // quick console digest of anything with a name (console may mangle CJK; file is fine)
  const named = b.filter(e => e.tags && e.tags.name);
  console.log('named buildings:', named.length);
})();

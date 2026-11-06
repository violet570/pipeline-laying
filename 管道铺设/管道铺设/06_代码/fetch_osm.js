// Fetch Yanshan University West Campus OSM data via Overpass API.
// Working mirror: overpass.openstreetmap.fr (requires browser-like Referer/UA)
// Fallback mirror: maps.mail.ru
const fs = require('fs');
const path = require('path');

const MIRRORS = [
  'https://overpass.openstreetmap.fr/api/interpreter?data=',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter?data=',
];
const HEADERS = {
  'Referer': 'https://overpass-turbo.eu/',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  'Accept': '*/*',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
};
const BBOX = '(39.9020,119.5040,39.9205,119.5325)';
const OUT_DIR = path.join(__dirname, '..', 'data', 'raw');
fs.mkdirSync(OUT_DIR, { recursive: true });

// Split campus bbox into 4 quadrants for heavy geometry queries
const QUADS = {
  NW: '(39.9112,119.5040,39.9205,119.5182)',
  NE: '(39.9112,119.5182,39.9205,119.5325)',
  SW: '(39.9020,119.5040,39.9112,119.5182)',
  SE: '(39.9020,119.5182,39.9112,119.5325)',
};

const QUERIES = {
  buildings: {
    parts: Object.values(QUADS).map(b => `[out:json][timeout:180];way["building"]${b};out geom;`),
    chunks: 4,
  },
  roads: { parts: [`[out:json][timeout:180];way["highway"]${BBOX};out geom;`], chunks: 1 },
  areas: { parts: [`[out:json][timeout:180];(way["landuse"]${BBOX};way["leisure"]${BBOX};way["natural"]${BBOX};way["amenity"="parking"]${BBOX};way["place"]${BBOX};);out geom;`], chunks: 1 },
  pois: { parts: [`[out:json][timeout:120];(node["amenity"]${BBOX};node["shop"]${BBOX};node["tourism"]${BBOX};node["man_made"]${BBOX};node["power"]${BBOX};node["barrier"]${BBOX};node["entrance"]${BBOX};);out;`], chunks: 1 },
  campus_boundary: { parts: [`[out:json][timeout:60];(way(696074149);way(695983911););out geom;`], chunks: 1 },
};

function mergeElements(parts) {
  const out = [];
  for (const p of parts) if (p && p.elements) out.push(...p.elements);
  return { version: 0.6, generator: 'merged', elements: out };
}

async function fetchQuery(query, attempt) {
  const mirror = MIRRORS[(attempt - 1) % MIRRORS.length];
  const url = mirror + encodeURIComponent(query);
  const res = await fetch(url, { headers: HEADERS, signal: AbortSignal.timeout(300000) });
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status} ${text.slice(0, 100)}`);
  const json = JSON.parse(text);
  return json;
}

async function fetchPart(query, label) {
  let lastErr;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const t0 = Date.now();
    try {
      const json = await fetchQuery(query, attempt);
      console.log(`  ${label} ok (attempt ${attempt}, ${((Date.now() - t0) / 1000).toFixed(1)}s, ${json.elements.length} el)`);
      return json;
    } catch (e) {
      lastErr = e;
      console.log(`  ${label} attempt ${attempt} failed: ${String(e.message).slice(0, 120)}`);
      await new Promise(r => setTimeout(r, 3000 * attempt));
    }
  }
  throw lastErr;
}

(async () => {
  const manifest = [];
  for (const [name, cfg] of Object.entries(QUERIES)) {
    console.log(`\n== ${name}: ${cfg.parts.length} part(s)`);
    const t0 = Date.now();
    const results = [];
    for (let i = 0; i < cfg.parts.length; i++) {
      try {
        results.push(await fetchPart(cfg.parts[i], `part${i + 1}`));
      } catch (e) {
        console.error(`${name} part${i + 1} FAILED`, e.message);
      }
    }
    if (!results.length) { console.error(`${name} completely failed`); continue; }
    const merged = results.length === 1 ? results[0] : mergeElements(results);
    const file = path.join(OUT_DIR, name + '.json');
    fs.writeFileSync(file, JSON.stringify(merged));
    const size = fs.statSync(file).size;
    console.log(`== ${name}: ${merged.elements.length} elements, ${(size / 1024).toFixed(1)} KB, ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    manifest.push({ name, elements: merged.elements.length, bytes: size });
  }
  fs.writeFileSync(path.join(OUT_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log('\nDONE');
})();

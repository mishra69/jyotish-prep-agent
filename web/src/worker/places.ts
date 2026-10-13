/**
 * Place autocomplete for the birth-place field, proxied to Photon.
 *
 * Photon rather than Nominatim (which the Python app used): Nominatim's usage
 * policy forbids autocomplete, Photon is built for it. Photon's public API asks
 * for fair use, so answers are cached at the edge -- "Varan" is fetched once,
 * not once per astrologer per keystroke.
 */

export type Place = { label: string; latitude: number; longitude: number };

type PhotonFeature = {
  geometry: { coordinates: [number, number] }; // [lon, lat]
  properties: {
    name?: string;
    state?: string;
    country?: string;
    osm_key?: string;
    osm_value?: string;
  };
};

const PHOTON_URL = 'https://photon.komoot.io/api/';
const CACHE_SECONDS = 60 * 60 * 24 * 7; // place names do not move
const MIN_QUERY = 3;

// Settlements and administrative areas: somewhere a person can be born.
// Excludes streets, shops, and the like that Photon also returns.
const PLACE_KEYS = new Set(['place', 'boundary']);

export function toPlaces(features: PhotonFeature[]): Place[] {
  const seen = new Set<string>();
  const places: Place[] = [];
  for (const f of features) {
    const p = f.properties;
    if (!p.name || !PLACE_KEYS.has(p.osm_key ?? '')) continue;
    const label = [p.name, p.state, p.country].filter(Boolean).join(', ');
    // Photon often returns a city and its same-named district a few km apart;
    // for a birth chart they are the same answer, and the first is the city.
    if (seen.has(label)) continue;
    seen.add(label);
    const [longitude, latitude] = f.geometry.coordinates;
    places.push({ label, latitude, longitude });
  }
  return places.slice(0, 6);
}

export async function searchPlaces(query: string, ctx: ExecutionContext): Promise<Response> {
  const q = query.trim().toLowerCase().replace(/\s+/g, ' ');
  if (q.length < MIN_QUERY) return Response.json([]);

  const cacheKey = new Request(`https://places.cache/v1?q=${encodeURIComponent(q)}`);
  const cache = caches.default;
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const url = `${PHOTON_URL}?${new URLSearchParams({ q, limit: '12', lang: 'en' })}`;
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      headers: { 'User-Agent': 'jyotish-prep (astrologer consultation prep)' },
      signal: AbortSignal.timeout(8_000),
    });
  } catch {
    return Response.json({ error: 'Place search is unavailable right now.' }, { status: 502 });
  }
  if (!upstream.ok) {
    return Response.json({ error: `Place search failed (${upstream.status}).` }, { status: 502 });
  }

  const { features } = (await upstream.json()) as { features: PhotonFeature[] };
  const res = Response.json(toPlaces(features), {
    headers: { 'Cache-Control': `public, max-age=${CACHE_SECONDS}` },
  });
  ctx.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}

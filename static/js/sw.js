/* LigtasPH offline-resilience Service Worker (map page).
 *
 * Strategy (disaster-safe, conservative):
 *  - App shell + static assets + GeoJSON datasets + last API payloads:
 *    cache-first, then network-fill on first visit.
 *  - Mapbox tiles/sprites/fonts (cross-origin): runtime cache after a
 *    successful 200 opaque response, stale-while-revalidate, so a repeat map
 *    view works during connectivity loss. RANGE requests are skipped (Mapbox
 *    font glyphs use them; caching those can serve corrupted glyphs).
 *  - Everything else: network-first with cache fallback.
 */
const VERSION = 'ligtasph-sw-v1';
const PRECACHE = [
  '/',
  '/map',
  '/static/css/main.css',
  '/static/js/prefs.js',
  '/static/js/announcements.js',
  '/static/js/home_banner.js',
  '/static/js/settings.js',
  '/api/evac-centers.geojson',
  '/static/noah/flood_mm_5yr.geojson',
  '/static/noah/landslide_mm.geojson',
  '/static/noah/stormsurge_ssa1.geojson',
  '/static/noah/stormsurge_ssa2.geojson',
  '/static/noah/stormsurge_ssa3.geojson',
  '/static/noah/stormsurge_ssa4.geojson',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function isMapboxAsset(url) {
  const h = url.hostname;
  return h === 'api.mapbox.com' && !url.searchParams.has('drive_through') && !String(url.pathname).includes('/directions');
}

function cacheableGet(request) {
  const m = request.method || 'GET';
  if (m !== 'GET') return false;
  // Range requests (glyphs) produce 206s that we won't cache.
  if (request.headers.get('range')) return false;
  return true;
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Only same-origin + Mapbox assets.
  if (url.origin !== location.origin && !isMapboxAsset(url)) return;
  const request = event.request;
  if (!cacheableGet(request)) return;

  // 1) Our own app + data: cache-first.
  if (url.origin === location.origin) {
    event.respondWith(
      caches.match(request).then((hit) => {
        if (hit) return hit;
        return fetch(request).then((res) => {
          if (res && res.ok && PRECACHE.includes(url.pathname)) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(request, copy));
          }
          return res;
        }).catch(() => caches.match('/map'));
      })
    );
    return;
  }

  // 2) Mapbox tiles/fonts/sprites: stale-while-revalidate (network first when online).
  if (isMapboxAsset(url)) {
    event.respondWith(
      fetch(request).then((res) => {
        if (res && (res.ok || res.type === 'opaque')) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(request, copy));
        }
        return res;
      }).catch(() => caches.match(request))
    );
  }
});
/**
 * Mobile App Suite — Service Worker
 * Strategy:
 *   - Static assets (CSS, JS, icons, fonts): cache-first
 *   - HTML pages: network-first with offline fallback
 *   - API / upload / download routes: network-only
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE  = `suite-static-${CACHE_VERSION}`;
const PAGE_CACHE    = `suite-pages-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  '/static/css/mobile.css',
  '/static/js/mobile.js',
  '/static/icons/suite-192.png',
  '/static/icons/suite-512.png',
  '/static/icons/audio-192.png',
  '/static/icons/audio-512.png',
  '/static/icons/pdf-192.png',
  '/static/icons/pdf-512.png',
  '/static/icons/ssh-192.png',
  '/static/icons/ssh-512.png',
  '/static/icons/email-192.png',
  '/static/icons/email-512.png',
  '/static/icons/flash-192.png',
  '/static/icons/flash-512.png',
];

const PRECACHED_PAGES = [
  '/',
  '/audio',
  '/pdf',
  '/ssh',
  '/email',
  '/flash',
];

const NETWORK_ONLY_PATTERNS = [
  /\/audio\/generate/,
  /\/audio\/delete/,
  /\/pdf\/upload/,
  /\/pdf\/fill/,
  /\/pdf\/download/,
  /\/ssh\//,
  /\/email\/generate/,
  /\/flash\/generate/,
  /\/julisunkan/,
  /\/set-lang/,
  /socket\.io/,
];

// ── Install ────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then(cache => cache.addAll(STATIC_ASSETS)),
      caches.open(PAGE_CACHE).then(cache => cache.addAll(PRECACHED_PAGES)),
    ]).then(() => self.skipWaiting())
  );
});

// ── Activate — clean old caches ────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== STATIC_CACHE && k !== PAGE_CACHE)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ──────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin GET requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Network-only for dynamic/API routes
  if (NETWORK_ONLY_PATTERNS.some(re => re.test(url.pathname))) return;

  // Cache-first for static assets
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then(c => c.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Network-first for HTML pages
  event.respondWith(
    fetch(request)
      .then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(PAGE_CACHE).then(c => c.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request).then(cached => cached || caches.match('/')))
  );
});

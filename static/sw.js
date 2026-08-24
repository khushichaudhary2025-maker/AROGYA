const CACHE_NAME = 'arogya-map-cache-v1';
const ASSETS_TO_CACHE = [
  '/static/arogya.jpeg'
];

// On install, cache basic offline assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

// Intercept tile and asset fetches to serve offline
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Check if this is an OpenStreetMap map tile request
  if (url.hostname.includes('tile.openstreetmap.org')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          // Cache hit: serve tile from cache
          if (cachedResponse) {
            return cachedResponse;
          }
          // Cache miss: fetch from network and store in cache
          return fetch(event.request).then(networkResponse => {
            if (networkResponse && networkResponse.status === 200) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          }).catch(() => {
            // Offline fallback if network is completely down and not cached
            return new Response('Offline tile unavailable', { status: 404 });
          });
        });
      })
    );
    return;
  }
  
  // Regular asset handler
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request);
    }).catch(() => {
      // Fallback
      return new Response('Network request failed', { status: 503 });
    })
  );
});

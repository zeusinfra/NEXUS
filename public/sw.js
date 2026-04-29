const CACHE_NAME = 'zeus-mobile-v1';
const ASSETS_TO_CACHE = [
  '/static/mobile.html',
  '/static/manifest.json',
  'https://cdn.socket.io/4.7.2/socket.io.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching offline assets');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[Service Worker] Removing old cache', key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Ignora requisições de API e Websocket
  if (event.request.url.includes('/api/') || event.request.url.includes('/ws') || event.request.url.includes('socket.io/?')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      
      return fetch(event.request).catch(() => {
        // Fallback for offline mode if trying to reach navigation
        if (event.request.mode === 'navigate') {
          return caches.match('/static/mobile.html');
        }
      });
    })
  );
});

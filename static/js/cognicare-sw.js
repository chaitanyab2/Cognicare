/**
 * Cognicare Service Worker
 * Version: cognicare-v1
 *
 * Privacy-First & Reliability-Focused Caching Architecture:
 * - Cache-First for static assets (/static/)
 * - Network-First for HTML navigation with reliable fallback to self-contained /offline/
 * - STRICTLY NETWORK-ONLY for non-GET requests, /media/ uploads, /accounts/, and /admin/
 * - No private memories, routines, or caregiver data stored in CacheStorage
 */

const CACHE_NAME = 'cognicare-v1';

const PRECACHE_ASSETS = [
  '/offline/',
  '/static/manifest.webmanifest',
  '/static/css/cognicare.css',
  '/static/js/cognicare-pwa.js',
  '/static/js/cognicare-voice.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-maskable-192.png',
  '/static/icons/icon-maskable-512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/favicon.png',
  '/static/icons/icon.svg'
];

// Install: Pre-cache core shell & offline fallback
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => {
      return self.skipWaiting();
    })
  );
});

// Activate: Clean up stale caches & claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// Fetch: Strategy dispatcher based on request type
self.addEventListener('fetch', (event) => {
  // Never intercept non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  const url = new URL(event.request.url);

  // Cross-origin requests: ignore (default browser fetch)
  if (url.origin !== self.location.origin) {
    return;
  }

  // Never cache private media uploads, accounts auth, or admin
  if (url.pathname.startsWith('/media/') ||
      url.pathname.startsWith('/accounts/') ||
      url.pathname.startsWith('/admin/')) {
    return;
  }

  // 1. Navigation requests (HTML pages): Network-First with Offline Fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        const offlinePage = await cache.match('/offline/');
        if (offlinePage) {
          return offlinePage;
        }
        return cache.match('/offline');
      })
    );
    return;
  }

  // 2. Static assets (/static/): Cache-First with runtime caching
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(event.request).then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200) {
            return networkResponse;
          }
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
          return networkResponse;
        });
      })
    );
    return;
  }

  // 3. Fallback to default network fetch for other requests
});

// Message listener for skip waiting prompt
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

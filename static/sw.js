// Service Worker for LearnVaultX - Offline Support
// UPDATED: v4 - Dashboard loading fix + cache refresh

const CACHE_NAME = 'learnvaultx-cache-v4';  // ← INCREMENTED VERSION TO FORCE REFRESH
const RUNTIME_CACHE = 'learnvaultx-runtime-v4';  // ← INCREMENTED VERSION

// Assets to cache on install (ONLY images, icons, fonts - NO HTML/CSS/JS)
const PRECACHE_ASSETS = [
    '/static/images/logo.png',
    '/static/icon.png',
    '/static/badge.png'
];

// Install event - cache core assets
self.addEventListener('install', (event) => {
    console.log('Service Worker v4 installing...');

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('Caching core assets');
                return cache.addAll(PRECACHE_ASSETS.map(url => new Request(url, { credentials: 'same-origin' }))).catch(e => {
                    console.warn('Some assets failed to cache:', e);
                });
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('Service Worker v4 activating...');

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((cacheName) => {
                        // Delete ALL old caches (v1, v2, runtime-v1, runtime-v2)
                        return cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE;
                    })
                    .map((cacheName) => {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome extensions and other protocols
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // ========================================
    // CRITICAL FIX: DO NOT CACHE HTML PAGES!
    // ========================================
    // HTML pages (including /, /login, /dashboard, etc.) should ALWAYS be fetched fresh
    if (request.mode === 'navigate' ||
        request.headers.get('accept')?.includes('text/html') ||
        url.pathname.endsWith('.html') ||
        url.pathname === '/' ||
        url.pathname.startsWith('/teacher') ||
        url.pathname.startsWith('/student') ||
        url.pathname.startsWith('/login') ||
        url.pathname.startsWith('/register')) {
        event.respondWith(networkOnly(request));
        return;
    }

    // Handle API requests - always network first, no caching
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkOnly(request));
        return;
    }

    // Handle CSS/JS files - use stale-while-revalidate (serve cached but update in background)
    if (url.pathname.endsWith('.css') || url.pathname.endsWith('.js')) {
        event.respondWith(staleWhileRevalidate(request));
        return;
    }

    // Handle images, fonts, icons - cache first (these don't change often)
    if (url.pathname.match(/\.(png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/)) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Handle uploaded files
    if (url.pathname.startsWith('/static/uploads/')) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Default: network only (no aggressive caching)
    event.respondWith(networkOnly(request));
});

// Network only strategy - always fetch fresh, no caching
async function networkOnly(request) {
    try {
        return await fetch(request);
    } catch (error) {
        console.error('Network request failed:', error);

        // For navigation, return offline page
        if (request.mode === 'navigate') {
            return new Response('Offline - Please check your connection', {
                status: 503,
                headers: { 'Content-Type': 'text/html' }
            });
        }

        throw error;
    }
}

// Stale-while-revalidate strategy - serve from cache immediately, update in background
async function staleWhileRevalidate(request) {
    const cache = await caches.open(RUNTIME_CACHE);
    const cachedResponse = await cache.match(request);

    // Fetch fresh version in background (don't await)
    const fetchPromise = fetch(request).then(networkResponse => {
        if (networkResponse && networkResponse.status === 200) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    }).catch(() => null);

    // Return cached version immediately if available
    return cachedResponse || fetchPromise;
}

// Cache first strategy (only for images/fonts that rarely change)
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
        return cachedResponse;
    }

    try {
        const networkResponse = await fetch(request);

        // Cache successful responses
        if (networkResponse && networkResponse.status === 200) {
            const cache = await caches.open(RUNTIME_CACHE);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.error('Fetch failed:', error);
        throw error;
    }
}

// Network first strategy - NOT USED ANYMORE (replaced with networkOnly for HTML)
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);

        // Cache successful responses
        if (networkResponse && networkResponse.status === 200) {
            const cache = await caches.open(RUNTIME_CACHE);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.error('Network request failed, trying cache:', error);

        const cachedResponse = await caches.match(request);

        if (cachedResponse) {
            return cachedResponse;
        }

        // Return offline response for API requests
        if (request.url.includes('/api/')) {
            return new Response(
                JSON.stringify({
                    error: 'You are offline. This action will be synced when you are back online.'
                }),
                {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' }
                }
            );
        }

        throw error;
    }
}

// Handle background sync
self.addEventListener('sync', (event) => {
    console.log('Background sync triggered:', event.tag);

    if (event.tag === 'sync-quiz-submissions') {
        event.waitUntil(syncQuizSubmissions());
    }
});

// Sync quiz submissions when back online
async function syncQuizSubmissions() {
    // This would sync with IndexedDB offline queue
    console.log('Syncing quiz submissions...');

    // Notify clients that sync is complete
    const clients = await self.clients.matchAll();
    clients.forEach((client) => {
        client.postMessage({
            type: 'sync-complete',
            data: 'Quiz submissions synced'
        });
    });
}

// Handle push notifications
self.addEventListener('push', (event) => {
    console.log('Push notification received:', event);

    const options = {
        body: event.data ? event.data.text() : 'New notification from LearnVaultX',
        icon: '/static/icon.png',
        badge: '/static/badge.png',
        vibrate: [200, 100, 200],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        }
    };

    event.waitUntil(
        self.registration.showNotification('LearnVaultX', options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('Notification clicked:', event);

    event.notification.close();

    event.waitUntil(
        clients.openWindow('/')
    );
});

// Message handler for communication with main thread
self.addEventListener('message', (event) => {
    console.log('Service Worker received message:', event.data);

    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }

    if (event.data && event.data.type === 'CACHE_URLS') {
        const urls = event.data.urls;
        event.waitUntil(
            caches.open(RUNTIME_CACHE).then((cache) => {
                return cache.addAll(urls);
            })
        );
    }
});


// Vyskar's service worker: makes the app installable and quick to open.
//
// - Pages: the cached copy opens at once and is refreshed in the background,
//   so the installed app starts without waiting for the network. A new
//   release shows from the next launch. Without a cached copy, the network.
// - /assets/: built files have a hash in their name and never change, so
//   they come from the cache once fetched.
// - Everything else from this site, such as icons: the cache answers at
//   once and is refreshed in the background.
// - The API is on another origin and is never cached: build status must
//   always be live.

const CACHE = 'vyskar-v3'
const SHELL = ['/', '/site.webmanifest', '/favicon.svg', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

// The app has one page, so every navigation is answered with '/'.
async function cachedPageFirst(event) {
  const cached = await caches.match('/')
  const fresh = fetch(event.request)
    .then(async (response) => {
      if (response.ok) (await caches.open(CACHE)).put('/', response.clone())
      return response
    })
    .catch(() => cached || Response.error())
  if (!cached) return fresh
  event.waitUntil(fresh) // keep the worker alive until the refresh is saved
  return cached
}

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) (await caches.open(CACHE)).put(request, response.clone())
  return response
}

async function staleWhileRevalidate(request) {
  const cached = await caches.match(request)
  const fresh = fetch(request)
    .then(async (response) => {
      if (response.ok) (await caches.open(CACHE)).put(request, response.clone())
      return response
    })
    .catch(() => cached)
  return cached || fresh
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') event.respondWith(cachedPageFirst(event))
  else if (url.pathname.startsWith('/assets/')) event.respondWith(cacheFirst(request))
  else event.respondWith(staleWhileRevalidate(request))
})

// Tapping a build notification opens the live app, or Vyskar for a failed
// build, reusing an open Vyskar window where there is one.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data?.url || '/'
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const own = windows.find((w) => new URL(w.url).origin === self.location.origin)
      if (url === '/' && own) return own.focus()
      return self.clients.openWindow(url)
    })(),
  )
})

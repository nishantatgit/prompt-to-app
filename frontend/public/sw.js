// Vyskar's service worker: makes the app installable and quick to open.
//
// - Pages: network first, so a new release shows at once; the cached copy
//   is only used offline.
// - /assets/: built files have a hash in their name and never change, so
//   they come from the cache once fetched.
// - Everything else from this site, such as icons: the cache answers at
//   once and is refreshed in the background.
// - The API is on another origin and is never cached: build status must
//   always be live.

const CACHE = 'vyskar-v1'
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

async function networkFirst(request) {
  try {
    const response = await fetch(request)
    const cache = await caches.open(CACHE)
    cache.put('/', response.clone())
    return response
  } catch {
    return (await caches.match('/')) || Response.error()
  }
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

  if (request.mode === 'navigate') event.respondWith(networkFirst(request))
  else if (url.pathname.startsWith('/assets/')) event.respondWith(cacheFirst(request))
  else event.respondWith(staleWhileRevalidate(request))
})

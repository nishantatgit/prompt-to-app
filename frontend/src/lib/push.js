// Web Push: the server tells this device a build finished, even when Vyskar
// is closed. notify.js covers the case where the page is still running.
//
// Only when the server has push on (VAPID keys set), the browser supports
// it, notifications are allowed and the service worker is running. On an
// iPhone that means the installed app (iOS 16.4 and later). Anything
// missing: no push, and nothing on screen, since the build works the same.

import { getPush, watchJobWithPush } from './api.js'

export function pushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

// The server's public key is base64url; subscribe() takes the raw bytes.
export function keyBytes(base64url) {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0))
}

function sameKey(subscription, key) {
  const current = subscription.options?.applicationServerKey
  if (!current) return true // the browser doesn't say: keep it
  const a = new Uint8Array(current)
  const b = keyBytes(key)
  return a.length === b.length && a.every((byte, i) => byte === b[i])
}

let serverKey // the server's answer, asked once per page load

async function publicKey() {
  if (serverKey === undefined) {
    const status = await getPush().catch(() => null)
    serverKey = status?.enabled && status.public_key ? status.public_key : null
  }
  return serverKey
}

// Ask the server to push this device when the job finishes. Call it after
// the notification question has been answered.
export async function watchBuild(jobId) {
  if (!pushSupported() || Notification.permission !== 'granted') return false
  try {
    const key = await publicKey()
    if (!key) return false
    const registration = await navigator.serviceWorker.getRegistration()
    if (!registration) return false
    let subscription = await registration.pushManager.getSubscription()
    if (subscription && !sameKey(subscription, key)) {
      // The server's keys changed: the old subscription can't be pushed to.
      await subscription.unsubscribe()
      subscription = null
    }
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(key),
      })
    }
    await watchJobWithPush(jobId, subscription.toJSON())
    return true
  } catch {
    // A missed push is not worth an error on screen.
    return false
  }
}

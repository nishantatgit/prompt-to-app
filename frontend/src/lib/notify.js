// Build notifications: a build takes minutes, so people switch away. When it
// finishes while Vyskar is in the background, a notification says so.
//
// This works while the page or the installed app is still running in the
// background. Notifying a phone whose app has been closed needs Web Push
// from the server, which comes later.

export function notificationsSupported() {
  return typeof window !== 'undefined' && 'Notification' in window
}

// Ask once, when the user starts a build: browsers only allow the question
// after a click, and it makes sense at that moment.
export async function askToNotify() {
  if (!notificationsSupported() || Notification.permission !== 'default') return
  try {
    await Notification.requestPermission()
  } catch {
    // Older Safari takes a callback instead; skipping is fine.
  }
}

export function buildMessage(job) {
  if (job?.status === 'succeeded') {
    return {
      title: 'Your app is live',
      body: job.confidence != null ? `Tests passed: ${job.confidence}%. Tap to open it.` : 'Tap to open it.',
      url: job.deploy_url || '/',
    }
  }
  if (job?.status === 'failed' || job?.status === 'rejected') {
    return { title: 'Your build stopped', body: 'Tap to see what happened.', url: '/' }
  }
  return null // cancelled by the user, or unknown: nothing to tell them
}

export async function notifyBuildDone(job) {
  const message = buildMessage(job)
  if (!message || !notificationsSupported() || Notification.permission !== 'granted') return
  if (document.visibilityState === 'visible') return // they are looking at it already
  const options = {
    body: message.body,
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: job.job_id,
    data: { url: message.url },
  }
  try {
    const registration = await navigator.serviceWorker?.getRegistration()
    if (registration) await registration.showNotification(message.title, options)
    else new Notification(message.title, options)
  } catch {
    // A missed notification is not worth an error on screen.
  }
}

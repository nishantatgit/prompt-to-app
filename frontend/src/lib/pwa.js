import { useEffect, useState } from 'react'

// Register the service worker in production builds only: in development it
// would serve stale files while editing.
export function registerServiceWorker() {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // The app works the same without it; installing is what is lost.
    })
  })
}

function isStandalone() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
  )
}

// iPhone or iPad. Since iPadOS 13, Safari on an iPad asks for desktop sites
// and says it is a Mac, so an iPad is a "Mac" with a touch screen (Macs
// report no touch points).
export function isIos(nav = window.navigator) {
  if (/iphone|ipad|ipod/i.test(nav.userAgent)) return true
  return /macintosh/i.test(nav.userAgent) && nav.maxTouchPoints > 1
}

// What the install button can offer on this device:
// - "prompt": the browser can install the app (Chrome, Edge, Android)
// - "ios": Safari installs from the Share menu, so explain that instead
// - null: already installed, or the browser cannot install apps
export function useInstall() {
  const [deferred, setDeferred] = useState(null)
  const [installed, setInstalled] = useState(() => isStandalone())

  useEffect(() => {
    const onPrompt = (event) => {
      event.preventDefault()
      setDeferred(event)
    }
    const onInstalled = () => {
      setInstalled(true)
      setDeferred(null)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  async function install() {
    if (!deferred) return
    deferred.prompt()
    const { outcome } = await deferred.userChoice
    if (outcome === 'accepted') setInstalled(true)
    setDeferred(null)
  }

  if (installed) return { kind: null, install }
  if (deferred) return { kind: 'prompt', install }
  if (isIos()) return { kind: 'ios', install }
  return { kind: null, install }
}

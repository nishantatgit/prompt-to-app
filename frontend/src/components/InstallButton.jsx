import { useState } from 'react'
import { useInstall } from '../lib/pwa.js'

// "Install app" where the browser can install it; on iPhone and iPad, a
// short note on adding it from the Share menu, since Safari has no prompt.
export default function InstallButton() {
  const { kind, install } = useInstall()
  const [showHint, setShowHint] = useState(false)

  if (!kind) return null

  if (kind === 'prompt') {
    return (
      <button type="button" onClick={install} className="min-h-11 whitespace-nowrap rounded-full px-3 text-sm text-muted hover:text-fg">
        Install app
      </button>
    )
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setShowHint((v) => !v)}
        aria-expanded={showHint}
        className="min-h-11 whitespace-nowrap rounded-full px-3 text-sm text-muted hover:text-fg"
      >
        Install app
      </button>
      {showHint && (
        <p
          role="note"
          className="fixed inset-x-4 top-20 z-10 mx-auto max-w-sm rounded-xl border border-line bg-card p-3 text-sm text-muted shadow-lg"
        >
          Tap the Share button in Safari, then <span className="text-fg">Add to Home Screen</span>.
        </p>
      )}
    </div>
  )
}

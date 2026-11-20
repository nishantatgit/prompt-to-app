import { useState } from 'react'

const SHOWN = 4

function ago(time) {
  const minutes = Math.round((Date.now() - time) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

// The apps built in this browser, each with a link and a way to change it.
export default function MyApps({ apps, onChange, disabled }) {
  const [all, setAll] = useState(false)
  if (!apps.length) return null
  const shown = all ? apps : apps.slice(0, SHOWN)
  return (
    <section aria-labelledby="my-apps" className="flex flex-col gap-3">
      <h2 id="my-apps" className="font-display text-sm font-bold uppercase tracking-[0.1em] text-dim">
        Your apps
      </h2>
      <ul className="flex flex-col divide-y divide-line rounded-2xl border border-line bg-card">
        {shown.map((app) => (
          <li key={app.name} className="flex items-center gap-3 px-4 py-2">
            {/* The whole name and prompt is the link, so it is big enough to tap. */}
            <a href={app.url} target="_blank" rel="noreferrer" className="flex min-h-11 min-w-0 flex-1 flex-col justify-center py-1">
              <span className="block truncate font-mono text-sm text-accent">{app.name}</span>
              <span className="block truncate text-xs text-dim">
                {app.prompt ? `${app.prompt} · ` : ''}
                {ago(app.updatedAt)}
              </span>
            </a>
            {app.editKey && (
              <button
                type="button"
                onClick={() => onChange(app)}
                disabled={disabled}
                className="min-h-11 shrink-0 rounded-full border border-wall px-4 text-sm text-muted hover:text-fg disabled:opacity-50"
              >
                Change
              </button>
            )}
          </li>
        ))}
      </ul>
      {apps.length > SHOWN && (
        <button type="button" onClick={() => setAll((v) => !v)} className="min-h-11 self-start text-sm text-muted underline underline-offset-4">
          {all ? 'Show fewer' : `Show all ${apps.length}`}
        </button>
      )}
    </section>
  )
}

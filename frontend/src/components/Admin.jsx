import { useCallback, useEffect, useState } from 'react'
import { NotAllowed, formatConfidence, formatCost, formatWhen, getFeedback, loadToken, saveToken } from '../lib/admin.js'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'feedback', label: 'Feedback' },
  { id: 'waitlist', label: 'Waitlist' },
]

function TokenForm({ onToken, error }) {
  const [value, setValue] = useState('')
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (value.trim()) onToken(value.trim())
      }}
      className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-5"
    >
      <label htmlFor="admin-token" className="text-sm text-muted">
        Admin token
      </label>
      <input
        id="admin-token"
        type="password"
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="min-h-11 rounded-xl border border-wall bg-ink px-3 font-mono text-fg focus:border-accent focus:outline-none"
      />
      <p className="text-xs text-dim">Kept in this tab only, and forgotten when it closes.</p>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={!value.trim()}
        className="min-h-11 rounded-full bg-accent px-5 font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-50"
      >
        Open
      </button>
    </form>
  )
}

function Build({ build }) {
  if (!build) return null
  const cost = formatCost(build.cost_usd)
  const confidence = formatConfidence(build.confidence)
  return (
    <div className="mt-3 flex flex-col gap-1 rounded-xl border border-line-2 bg-ink-2 px-3 py-2 text-sm">
      {build.prompt && <p className="text-fg">{build.prompt}</p>}
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        {build.status && <span>Status: {build.status}</span>}
        {build.trial && <span>Free build</span>}
        {cost && <span>Cost: {cost}</span>}
        {confidence && <span>Confidence: {confidence}</span>}
      </p>
      {build.reason && <p className="text-xs text-dim">{build.reason}</p>}
      {build.deploy_url ? (
        <a href={build.deploy_url} target="_blank" rel="noreferrer" className="truncate font-mono text-xs text-accent underline underline-offset-4">
          {build.app || build.deploy_url}
        </a>
      ) : (
        build.app && <p className="font-mono text-xs text-dim">{build.app}</p>
      )}
    </div>
  )
}

function Entry({ row }) {
  const waitlist = row.kind === 'waitlist'
  return (
    <li className="px-4 py-4">
      <p className="flex flex-wrap items-center gap-2 text-xs text-dim">
        <span className={`rounded-full px-2 py-0.5 font-semibold ${waitlist ? 'bg-plum text-accent' : 'bg-line-2 text-muted'}`}>
          {waitlist ? 'Waitlist' : 'Feedback'}
        </span>
        {row.rating && <span className="text-muted">{row.rating === 'up' ? 'Thumbs up' : 'Thumbs down'}</span>}
        <time dateTime={new Date(row.created * 1000).toISOString()}>{formatWhen(row.created)}</time>
      </p>
      {row.message && <p className="mt-2 whitespace-pre-wrap break-words text-fg">{row.message}</p>}
      {row.email && (
        <a href={`mailto:${row.email}`} className="mt-2 inline-block break-all text-sm text-accent underline underline-offset-4">
          {row.email}
        </a>
      )}
      <Build build={row.build} />
    </li>
  )
}

// /admin: feedback and waitlist emails, newest first, for whoever has ADMIN_TOKEN.
export default function Admin() {
  const [token, setToken] = useState(loadToken)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  // A token saved earlier in this tab loads straight away.
  const [loading, setLoading] = useState(() => Boolean(loadToken()))
  const [filter, setFilter] = useState('all')

  const fetchRows = useCallback(
    (given) =>
      getFeedback(given)
        .then(setRows)
        .catch((e) => {
          if (e instanceof NotAllowed) {
            saveToken('')
            setToken('')
            setRows(null)
          }
          setError(e.message || 'Could not load feedback.')
        })
        .finally(() => setLoading(false)),
    [],
  )

  const load = (given) => {
    setLoading(true)
    setError('')
    fetchRows(given)
  }

  useEffect(() => {
    document.title = 'Vyskar admin'
    const saved = loadToken()
    if (saved) fetchRows(saved)
  }, [fetchRows])

  const openWith = (given) => {
    saveToken(given)
    setToken(given)
    load(given)
  }

  const signOut = () => {
    saveToken('')
    setToken('')
    setRows(null)
    setError('')
  }

  const count = (kind) => (rows || []).filter((r) => kind === 'all' || r.kind === kind).length
  const shown = (rows || []).filter((r) => filter === 'all' || r.kind === filter)

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col gap-5 px-4 py-8">
      <header className="flex items-center justify-between gap-3">
        <h1 className="font-display text-xl font-bold">Feedback</h1>
        {token && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => load(token)}
              disabled={loading}
              className="min-h-11 rounded-full border border-wall px-4 text-sm text-muted hover:text-fg disabled:opacity-50"
            >
              {loading ? 'Loading' : 'Refresh'}
            </button>
            <button
              type="button"
              onClick={signOut}
              className="min-h-11 rounded-full border border-wall px-4 text-sm text-muted hover:text-fg"
            >
              Sign out
            </button>
          </div>
        )}
      </header>

      {!token && <TokenForm onToken={openWith} error={error} />}

      {token && error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {token && rows && (
        <>
          <div role="group" aria-label="Show" className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={filter === f.id}
                onClick={() => setFilter(f.id)}
                className={`min-h-11 rounded-full border px-4 text-sm ${
                  filter === f.id ? 'border-accent bg-accent text-on-accent' : 'border-wall text-muted hover:text-fg'
                }`}
              >
                {f.label} ({count(f.id)})
              </button>
            ))}
          </div>
          {shown.length ? (
            <ul className="flex flex-col divide-y divide-line rounded-2xl border border-line bg-card">
              {shown.map((row) => (
                <Entry key={row.id} row={row} />
              ))}
            </ul>
          ) : (
            <p className="text-muted">Nothing here yet.</p>
          )}
        </>
      )}

      {token && !rows && loading && <p className="text-muted">Loading feedback</p>}
    </main>
  )
}

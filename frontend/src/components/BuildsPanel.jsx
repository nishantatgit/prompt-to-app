import { useState } from 'react'
import { joinWaitlist } from '../lib/api.js'
import FeedbackForm from './FeedbackForm.jsx'

// Free builds left, or, when they are used up: feedback for more, and a
// way to get paid builds (the packs when buying is on, else an email list).
export default function BuildsPanel({ trial, credits, bonusBuilds, onBonus }) {
  const [email, setEmail] = useState('')
  const [joined, setJoined] = useState(false)
  const [error, setError] = useState('')
  const left = trial.builds_left

  async function join(e) {
    e.preventDefault()
    setError('')
    try {
      await joinWaitlist(email.trim())
      setJoined(true)
    } catch (err) {
      setError(err.message)
    }
  }

  if (left > 0) {
    return (
      <section aria-labelledby="builds-title" className="rounded-2xl border border-line bg-card p-6">
        <h2 id="builds-title" className="font-display text-lg font-bold">
          You have {left} free {left === 1 ? 'build' : 'builds'}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          No AI key needed. Each new app or change uses one.
        </p>
      </section>
    )
  }

  return (
    <section aria-labelledby="builds-title" className="flex flex-col gap-5 rounded-2xl border border-line bg-card p-6">
      <div>
        <h2 id="builds-title" className="font-display text-lg font-bold">You've used your free builds</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">Thanks for trying Vyskar!</p>
      </div>

      {trial.bonus_available && (
        <div className="flex flex-col gap-3">
          <p className="font-semibold">Tell us how it went and get {bonusBuilds} more builds.</p>
          <FeedbackForm withRating={false} withEmail autoOpen bonus={bonusBuilds} onBonus={onBonus} />
        </div>
      )}

      {!credits.enabled && (
        <div className="flex flex-col gap-2 border-t border-line pt-5">
          <p className="text-sm text-muted">Want more builds? Paid packs are coming soon.</p>
          {joined ? (
            <p className="text-sm text-accent">You're on the list. We'll email you first.</p>
          ) : (
            <form onSubmit={join} className="flex flex-col gap-2 sm:flex-row">
              <label htmlFor="waitlist-email" className="sr-only">Email</label>
              <input
                id="waitlist-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className="min-h-11 flex-1 rounded-xl border border-wall bg-ink px-3 text-base text-fg placeholder:text-dim"
              />
              <button type="submit" className="min-h-11 rounded-full border border-wall px-5 text-sm text-fg">
                Tell me
              </button>
            </form>
          )}
          {error && <p className="text-sm text-accent">{error}</p>}
        </div>
      )}
    </section>
  )
}

import { useState } from 'react'
import { sendFeedback } from '../lib/api.js'

const BONUS_MIN = 20 // characters, as the server counts them

function Thumb({ down, ...props }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={`h-5 w-5 ${down ? 'rotate-180' : ''}`} {...props}>
      <path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3Zm0 0 4-8a3 3 0 0 1 3 3v3h5a2 2 0 0 1 2 2.3l-1.4 8A2 2 0 0 1 17.6 21H7" />
    </svg>
  )
}

// Feedback about one build (with jobId), or about Vyskar in general.
// bonus: how many free builds a real message earns now, or 0.
export default function FeedbackForm({ jobId, bonus = 0, withRating = true, withEmail = false, onBonus, autoOpen = false }) {
  const [rating, setRating] = useState(null)
  const [message, setMessage] = useState('')
  const [email, setEmail] = useState('')
  const [open, setOpen] = useState(autoOpen)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(null)
  const [error, setError] = useState('')

  async function send(e) {
    e?.preventDefault()
    setSending(true)
    setError('')
    try {
      const reply = await sendFeedback({ jobId, rating, message: message.trim(), email: email.trim() })
      setSent(reply)
      if (reply.bonus_builds) onBonus?.(reply.bonus_builds)
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  if (sent) {
    return (
      <p className="text-sm text-accent">
        {sent.bonus_builds
          ? `Thank you! You've got ${sent.bonus_builds} more free builds.`
          : 'Thank you! This goes straight to the person building Vyskar.'}
      </p>
    )
  }

  const long = message.trim().length >= BONUS_MIN
  return (
    <form onSubmit={send} className="flex flex-col gap-3">
      {withRating && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">How did it go?</span>
          {[
            ['up', 'Good', false],
            ['down', 'Not right', true],
          ].map(([value, label, down]) => (
            <button
              key={value}
              type="button"
              aria-pressed={rating === value}
              onClick={() => {
                setRating(value)
                setOpen(true)
              }}
              className={`flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm ${
                rating === value ? 'border-accent text-accent' : 'border-wall text-muted hover:text-fg'
              }`}
            >
              <Thumb down={down} />
              {label}
            </button>
          ))}
        </div>
      )}
      {open && (
        <>
          <label className="sr-only" htmlFor={`feedback-${jobId || 'general'}`}>Your feedback</label>
          <textarea
            id={`feedback-${jobId || 'general'}`}
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={4000}
            placeholder={
              !withRating
                ? 'How did your builds go? What should Vyskar do better?'
                : rating === 'up'
                  ? 'What did you like? What would you build next? (optional)'
                  : 'What went wrong, or what did you expect?'
            }
            className="w-full resize-y rounded-xl border border-wall bg-ink p-3 text-base text-fg placeholder:text-dim"
          />
          {withEmail && (
            <>
              <label className="sr-only" htmlFor={`feedback-email-${jobId || 'general'}`}>Email, optional</label>
              <input
                id={`feedback-email-${jobId || 'general'}`}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email, if you'd like a reply (optional)"
                autoComplete="email"
                className="min-h-11 w-full rounded-xl border border-wall bg-ink px-3 text-base text-fg placeholder:text-dim"
              />
            </>
          )}
          {bonus > 0 && (
            <p className={`text-xs ${long ? 'text-accent' : 'text-dim'}`}>
              {long
                ? `Sending this gets you ${bonus} more free builds.`
                : `Write a sentence or two and get ${bonus} more free builds.`}
            </p>
          )}
          <button
            type="submit"
            disabled={sending || (!rating && !message.trim())}
            className="min-h-11 self-start rounded-full bg-accent px-6 text-sm font-semibold text-on-accent disabled:opacity-50"
          >
            {sending ? 'Sending...' : 'Send feedback'}
          </button>
        </>
      )}
      {error && <p className="text-sm text-accent">{error}</p>}
    </form>
  )
}

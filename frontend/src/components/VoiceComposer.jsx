import { useEffect, useRef, useState } from 'react'
import { listen, speechSupported } from '../lib/speech.js'

function MicIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8" />
    </svg>
  )
}

function StopIcon(props) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
    </svg>
  )
}

// The phone home screen: tap the mic, describe the app, then build it.
// Without a speech recognizer (iPhone home screen apps), the mic switches to
// typing, where the keyboard's own dictation mic works.
export default function VoiceComposer({
  prompt,
  onPromptChange,
  onBuild,
  canBuild,
  running,
  note,
  onType,
  compact = false, // once a build has started, so its progress shows below
}) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const session = useRef(null)

  useEffect(() => () => session.current?.stop(), [])

  function start() {
    if (!speechSupported()) {
      onType({ dictate: true })
      return
    }
    setError('')
    onPromptChange('')
    setListening(true)
    session.current = listen({
      onText: onPromptChange,
      onError: setError,
      onEnd: () => {
        setListening(false)
        session.current = null
      },
    })
  }

  function stop() {
    session.current?.stop()
  }

  const hasText = prompt.trim().length > 0
  const reviewing = hasText && !listening

  return (
    <section aria-label="Describe your app by voice" className={`flex flex-col items-center justify-center gap-8 text-center ${compact ? '' : 'min-h-[calc(100svh-12rem)]'}`}>
      <h1 className="font-display text-[26px] font-bold leading-tight">
        {listening ? 'Listening...' : reviewing ? 'Build this?' : 'What should we build?'}
      </h1>

      {!reviewing && (
        <div className="relative grid place-items-center">
          {listening && (
            <span aria-hidden="true" className="absolute h-36 w-36 rounded-full bg-accent/30 motion-safe:animate-ping" />
          )}
          <button
            type="button"
            onClick={listening ? stop : start}
            disabled={running}
            aria-pressed={listening}
            aria-label={listening ? 'Stop listening' : 'Tap and describe your app'}
            className="relative grid h-36 w-36 place-items-center rounded-full bg-accent text-on-accent shadow-[0_0_0_10px_rgba(80,234,242,0.12)] active:scale-95 disabled:opacity-50"
          >
            {listening ? <StopIcon className="h-12 w-12" /> : <MicIcon className="h-14 w-14" />}
          </button>
        </div>
      )}

      <div aria-live="polite" className="min-h-[3rem] w-full">
        {hasText ? (
          <p className={`text-lg leading-relaxed ${listening ? 'text-muted' : 'rounded-2xl border border-wall bg-card p-4 text-left text-fg'}`}>
            {prompt}
          </p>
        ) : (
          <p className="text-muted">
            {listening ? 'Describe your app, then tap stop.' : 'Tap the mic and describe your app in your own words.'}
          </p>
        )}
        {error && <p className="mt-3 text-sm text-accent">{error}</p>}
      </div>

      {reviewing && (
        <div className="flex w-full flex-col gap-3">
          <button
            type="button"
            onClick={onBuild}
            disabled={!canBuild}
            className="min-h-12 rounded-full bg-accent px-7 font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? 'Building...' : 'Build my app'}
          </button>
          <div className="grid grid-cols-2 gap-3">
            <button type="button" onClick={start} disabled={running} className="min-h-11 rounded-full border border-wall text-sm text-muted disabled:opacity-50">
              Say it again
            </button>
            <button type="button" onClick={() => onType({})} disabled={running} className="min-h-11 rounded-full border border-wall text-sm text-muted disabled:opacity-50">
              Edit the text
            </button>
          </div>
          {note && <p className="text-sm text-dim">{note}</p>}
        </div>
      )}

      {!reviewing && !listening && (
        <button type="button" onClick={() => onType({})} className="min-h-11 px-4 text-sm text-muted underline underline-offset-4">
          Type instead
        </button>
      )}
    </section>
  )
}

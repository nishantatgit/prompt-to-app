import { useEffect, useRef, useState } from 'react'
import { transcribe } from '../lib/api.js'
import { doneCue, startCue, stopCue } from '../lib/feedback.js'
import { recordingSupported, startRecording } from '../lib/recorder.js'
import { listen, speechSupported } from '../lib/speech.js'

const MAX_SECONDS = 30
const BARS = 28
const EXAMPLES = [
  'a habit tracker that shows my streaks',
  'a shared grocery list for my flat',
  'an RSVP page for my birthday party',
  'a tip calculator that splits the bill',
  'a notes app with login',
  'a quiz about Indian history',
]
const LANGUAGES = {
  'hi-IN': 'Hindi', 'bn-IN': 'Bengali', 'kn-IN': 'Kannada', 'ml-IN': 'Malayalam',
  'mr-IN': 'Marathi', 'od-IN': 'Odia', 'pa-IN': 'Punjabi', 'ta-IN': 'Tamil',
  'te-IN': 'Telugu', 'gu-IN': 'Gujarati',
}

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

function clock(seconds) {
  return `0:${String(Math.floor(seconds)).padStart(2, '0')}`
}

// Rotates through example apps while the mic waits.
function Examples({ examples = EXAMPLES }) {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => (i + 1) % examples.length), 3200)
    return () => clearInterval(timer)
  }, [examples])
  return (
    <p className="text-muted">
      Try saying{' '}
      <span key={index} className="voice-fade-in block text-fg">
        “{examples[index % examples.length]}”
      </span>
    </p>
  )
}

// The text, one word after another, once it is written down.
function RevealedText({ text }) {
  const words = text.split(' ')
  return (
    <p className="rounded-2xl border border-wall bg-card p-4 text-left text-lg leading-relaxed text-fg">
      {words.map((word, i) => (
        <span key={`${i}-${word}`} className="voice-word" style={{ animationDelay: `${Math.min(i, 40) * 45}ms` }}>
          {word}{' '}
        </span>
      ))}
    </p>
  )
}

// The phone home screen: tap the mic, describe the app, then build it.
//
// - serverVoice: the phone records and Sarvam writes it down, in English,
//   from any Indian language. Works in iPhone home screen apps too.
// - otherwise the browser's own recognizer, where there is one.
// - otherwise the mic switches to typing and keyboard dictation.
export default function VoiceComposer({
  prompt,
  onPromptChange,
  onBuild,
  canBuild,
  running,
  note,
  onType,
  serverVoice = false,
  title = 'What should we build?',
  buildLabel = 'Build my app',
  examples,
  compact = false, // once a build has started, so its progress shows below
}) {
  const [phase, setPhase] = useState('idle') // idle, listening, transcribing, review
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const [language, setLanguage] = useState(null)
  const session = useRef(null)
  const orb = useRef(null)
  const bars = useRef([])
  const history = useRef(new Array(BARS).fill(0))
  const recording = serverVoice && recordingSupported()

  useEffect(() => () => session.current?.cancel?.(), [])

  // While recording: the clock, and stopping by itself at the limit.
  useEffect(() => {
    if (phase !== 'listening' || !recording) return
    const timer = setInterval(() => {
      const seconds = session.current?.seconds() ?? 0
      setElapsed(seconds)
      if (seconds >= MAX_SECONDS - 0.5) finishRecording()
    }, 250)
    return () => clearInterval(timer)
  })

  // Drawn straight onto the elements: 40 updates a second through React
  // state would re-render the whole screen each time.
  function showLevel(level) {
    orb.current?.style.setProperty('--level', level.toFixed(3))
    history.current.push(level)
    history.current.shift()
    history.current.forEach((value, i) => {
      const bar = bars.current[i]
      if (bar) bar.style.transform = `scaleY(${0.12 + value * 0.88})`
    })
  }

  async function start() {
    setError('')
    setLanguage(null)
    if (recording) {
      try {
        session.current = await startRecording({ onLevel: showLevel })
      } catch (err) {
        setError(
          err?.name === 'NotAllowedError'
            ? 'Allow microphone access for Vyskar, then tap the mic again.'
            : "Couldn't start the microphone. Type your app instead.",
        )
        return
      }
      startCue()
      onPromptChange('')
      setElapsed(0)
      setPhase('listening')
      return
    }
    if (speechSupported()) {
      startCue()
      onPromptChange('')
      setPhase('listening')
      session.current = listen({
        onText: onPromptChange,
        onError: setError,
        onEnd: () => {
          session.current = null
          setPhase('review')
          stopCue()
        },
      })
      return
    }
    onType({ dictate: true })
  }

  async function finishRecording() {
    const current = session.current
    if (!current) return
    session.current = null
    stopCue()
    setPhase('transcribing')
    try {
      const { text, language: spoken } = await transcribe(current.stop())
      onPromptChange(text)
      setLanguage(spoken)
      setPhase('review')
      doneCue()
    } catch (err) {
      setError(err.message)
      setPhase('idle')
    }
  }

  function stop() {
    if (recording) finishRecording()
    else session.current?.stop()
  }

  const hasText = prompt.trim().length > 0
  const reviewing = phase === 'review' && hasText
  const listening = phase === 'listening'
  const transcribing = phase === 'transcribing'
  const progress = Math.min(1, elapsed / MAX_SECONDS)
  const RING = 2 * Math.PI * 86
  const spokenIn = LANGUAGES[language]

  return (
    <section
      aria-label="Describe your app by voice"
      className={`flex flex-col items-center justify-center gap-7 text-center ${compact ? '' : 'min-h-[calc(100svh-12rem)]'}`}
    >
      <h1 className="font-display text-[26px] font-bold leading-tight">
        {listening ? 'Listening...' : transcribing ? 'Got it' : reviewing ? `${buildLabel.replace(' my app', '')} this?` : title}
      </h1>

      {!reviewing && (
        <div ref={orb} className="voice-orb relative grid h-48 w-48 place-items-center" data-live={listening || undefined}>
          <span aria-hidden="true" className="voice-glow absolute inset-6 rounded-full bg-accent" />
          {listening && !recording && (
            <span aria-hidden="true" className="absolute h-36 w-36 rounded-full bg-accent/30 motion-safe:animate-ping" />
          )}
          {recording && listening && (
            <svg aria-hidden="true" viewBox="0 0 192 192" className="absolute inset-0 -rotate-90">
              <circle cx="96" cy="96" r="86" fill="none" stroke="currentColor" strokeWidth="4" className="text-line" />
              <circle
                cx="96" cy="96" r="86" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round"
                className={progress > 0.83 ? 'text-amber-300' : 'text-accent'}
                strokeDasharray={RING}
                strokeDashoffset={RING * (1 - progress)}
                style={{ transition: 'stroke-dashoffset 250ms linear' }}
              />
            </svg>
          )}
          <button
            type="button"
            onClick={listening ? stop : start}
            disabled={running || transcribing}
            aria-pressed={listening}
            aria-label={listening ? 'Stop listening' : 'Tap and describe your app'}
            className="voice-button relative grid h-36 w-36 place-items-center rounded-full bg-accent text-on-accent disabled:opacity-60"
          >
            {transcribing ? (
              <span className="voice-dots" aria-hidden="true"><i /><i /><i /></span>
            ) : listening ? (
              <StopIcon className="h-12 w-12" />
            ) : (
              <MicIcon className="h-14 w-14" />
            )}
          </button>
        </div>
      )}

      {recording && listening && (
        <div className="flex w-full flex-col items-center gap-3">
          <div aria-hidden="true" className="flex h-10 items-center gap-[3px]">
            {Array.from({ length: BARS }, (_, i) => (
              <span key={i} ref={(el) => (bars.current[i] = el)} className="voice-bar h-10 w-[5px] rounded-full bg-accent" />
            ))}
          </div>
          <p className="font-mono text-sm tabular-nums text-dim">
            {clock(elapsed)} / {clock(MAX_SECONDS)}
          </p>
        </div>
      )}

      <div aria-live="polite" className="min-h-[3rem] w-full">
        {reviewing ? (
          <>
            <RevealedText text={prompt} />
            {spokenIn && <p className="mt-2 text-sm text-dim">Heard in {spokenIn}, written in English.</p>}
          </>
        ) : listening && hasText ? (
          <p className="text-lg leading-relaxed text-muted">{prompt}</p>
        ) : listening ? (
          <p className="text-muted">Describe your app, then tap stop.</p>
        ) : transcribing ? (
          <p className="text-muted">Writing down what you said...</p>
        ) : (
          <Examples examples={examples} />
        )}
        {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      </div>

      {reviewing && (
        <div className="flex w-full flex-col gap-3">
          <button
            type="button"
            onClick={onBuild}
            disabled={!canBuild}
            className="min-h-12 rounded-full bg-accent px-7 font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? 'Building...' : buildLabel}
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

      {phase === 'idle' && (
        <button type="button" onClick={() => onType({})} className="min-h-11 px-4 text-sm text-muted underline underline-offset-4">
          Type instead
        </button>
      )}
    </section>
  )
}

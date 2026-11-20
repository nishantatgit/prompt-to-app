import { useEffect, useState } from 'react'

// While Vyskar builds, a photo of the app develops, like an instant photo:
// it starts as a rough pencil sketch under a dark, grainy, brownish blur and
// slowly clears into a crisp, colourful app, with a flash when it goes live.
//
// stage: index in JobView's STAGES (-1 before the first); done: the build
// succeeded. Between stages it keeps creeping toward the next stage's level,
// so it never stands still.
//
// shot: a photo of the real, live app, taken by the server after deploy.
// When the build succeeds, the drawing crossfades into it once it has loaded.
// Without one, or if it fails to load, the photo ends on the drawing.

const LEVELS = [0.06, 0.16, 0.28, 0.4, 0.52, 0.68, 0.82, 0.93]
const CREEP_MS = 40000 // time to drift most of the way to the next level

const CAPTIONS = [
  'Reading your idea',
  'Writing down what it must do',
  'Sketching the screens',
  'Setting up the project',
  'Building it',
  'Planning how to test it',
  'Testing it like a real user would',
  'Putting it online',
]

function useDevelopment(stage, done) {
  // Seconds spent in the current stage, counted by an interval.
  const [clock, setClock] = useState({ stage, seconds: 0 })
  if (clock.stage !== stage) setClock({ stage, seconds: 0 })
  useEffect(() => {
    if (done) return
    const timer = setInterval(() => setClock((c) => ({ ...c, seconds: c.seconds + 1 })), 1000)
    return () => clearInterval(timer)
  }, [done])
  if (done) return 1
  const from = LEVELS[Math.max(0, stage)] ?? 0.06
  const to = LEVELS[stage + 1] ?? 0.97
  const t = Math.min(1, (clock.seconds * 1000) / CREEP_MS)
  return from + (to - from) * 0.8 * (1 - (1 - t) ** 2) // eases in, never quite arrives
}

// The app in the photo. sketch: outlines only, like pencil on paper.
function AppShot({ sketch }) {
  const c = sketch ? 'dev-sketch' : 'dev-color'
  return (
    <div className={`dev-app ${c}`}>
      <div className="dev-hero">
        <span className="dev-avatar" />
        <span className="dev-title" />
        <span className="dev-sub" />
      </div>
      <div className="dev-stats">
        <span><b /> <i /></span>
        <span><b /> <i /></span>
        <span><b /> <i /></span>
      </div>
      <div className="dev-list">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="dev-row">
            <span className="dev-dot" />
            <span className="dev-line" style={{ width: `${[62, 48, 56, 44][i]}%` }} />
            <span className="dev-toggle" />
          </div>
        ))}
      </div>
    </div>
  )
}

// The real app, faded in over the drawing once its image has loaded.
function LiveShot({ src }) {
  const [state, setState] = useState('loading')
  if (state === 'failed') return null
  return (
    <img
      src={src}
      alt=""
      decoding="async"
      onLoad={() => setState('loaded')}
      onError={() => setState('failed')}
      className={`dev-shot ${state === 'loaded' ? 'dev-shot-in' : ''}`}
    />
  )
}

export default function BuildAnimation({ stage, done = false, shot = '' }) {
  const d = useDevelopment(stage, done)
  const caption = done ? 'Your app is live' : CAPTIONS[Math.max(0, stage)]
  // Every look is derived from how developed the photo is, 0 to 1.
  const look = {
    '--blur': `${(1 - d) * 7}px`,
    '--gray': 1 - d,
    '--sepia': (1 - d) * 0.75,
    '--contrast': 0.55 + 0.45 * d,
    '--bright': 0.55 + 0.45 * d,
    '--grain': (1 - d) * 0.55,
    '--sketch': Math.max(0, 1 - d * 1.7),
  }

  return (
    <figure className={`dev mt-5 flex flex-col items-center gap-4 ${done ? 'dev-done' : ''}`} aria-hidden="true" style={look}>
      <div className="dev-print">
        <div className="dev-photo">
          <AppShot />
          <div className="dev-sketch-layer">
            <AppShot sketch />
          </div>
          {done && shot && <LiveShot key={shot} src={shot} />}
          <div className="dev-grain" />
          <div className="dev-flash" />
          <div className="dev-gloss" />
        </div>
      </div>
      <figcaption key={caption} className="dev-caption text-sm text-muted">
        {caption}
        {!done && (
          <span className="ba-dots"><i>.</i><i>.</i><i>.</i></span>
        )}
      </figcaption>
    </figure>
  )
}

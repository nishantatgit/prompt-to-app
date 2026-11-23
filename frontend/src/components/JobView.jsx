import { useEffect, useState } from 'react'
import { cancelJob, getJob, screenshotUrl } from '../lib/api.js'
import FeedbackForm from './FeedbackForm.jsx'
import BuildAnimation from './BuildAnimation.jsx'

const STAGES = [
  'checking request',
  'requirements',
  'architecture',
  'setting up',
  'building',
  'planning tests',
  'testing',
  'deploying',
]
const POLL_MS = 2000
const FINISHED = new Set(['succeeded', 'failed', 'rejected', 'cancelled'])

// 12s, 1m 05s, 1h 02m.
function formatDuration(seconds) {
  if (seconds == null) return ''
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`
}

// The model cost, when every model used has a known price.
function costNote(job) {
  const usage = job.usage
  if (!usage?.complete || usage.cost_usd == null) return ''
  const cost = usage.cost_usd < 0.01 ? 'under $0.01' : `about $${usage.cost_usd.toFixed(2)}`
  return ` · ${cost} ${job.trial ? 'of free credit' : 'on your AI key'}`
}

// How long each step took, once the build has ended.
function StepTimes({ job }) {
  const stages = job?.timings?.stages ?? {}
  const shown = STAGES.filter((stage) => stages[stage])
  if (!shown.length) return null
  return (
    <div className="mt-5 flex flex-col gap-2">
      <p className="font-mono text-xs text-dim">
        Took {formatDuration(job.timings.total_seconds)}
        {costNote(job)}
      </p>
      <ul aria-label="Time per step" className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 font-mono text-xs">
        {shown.map((stage) => (
          <li key={stage} className="contents">
            <span className="text-muted">{stage}</span>
            <span className="text-right tabular-nums text-dim">{formatDuration(stages[stage].seconds)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function failureHeading(job) {
  if (job.status === 'rejected') return 'Vyskar could not build this request.'
  // Free and bought builds run on Vyskar's own AI key: when it stops
  // working midway, the visitor has nothing to fix.
  if (job.reason?.startsWith('paused')) return "Vyskar's AI stopped partway through."
  if (job.reason?.startsWith('key rejected')) return 'Your API key did not work.'
  if (job.reason?.startsWith('no credit')) return 'Your AI account is out of credit.'
  if (job.reason?.startsWith('internal error')) return 'Something went wrong on our side.'
  return 'The app did not pass its checks.'
}

// Shown under the steps while polling can't reach Vyskar. The build keeps
// running on the server, so the steps stay and polling carries on.
const OFFLINE_NOTE = "Can't reach Vyskar right now. Your build keeps going, and this page catches up once it's back."

// One short line for screen readers, changing only when the build moves
// on, so the timers ticking every poll are not read out.
function announcement(job, reached, error, offline) {
  if (error) return error
  if (offline) return OFFLINE_NOTE
  if (!job) return 'Starting the build.'
  if (job.status === 'queued') return 'Waiting for a free builder.'
  if (job.status === 'succeeded') return 'Your app is live.'
  if (job.status === 'cancelled') return 'Build cancelled.'
  if (job.status === 'failed' || job.status === 'rejected') return failureHeading(job)
  if (reached >= 0) return `Step ${reached + 1} of ${STAGES.length}: ${STAGES[reached]}.`
  return 'Starting the build.'
}

// The build loop's latest steps, such as "Writing src/App.jsx" or "Build 1 failed,
// fixing it". Only loop jobs have them; pipeline jobs show the steps alone.
const ACTIVITY_SHOWN = 6

function LoopActivity({ job }) {
  if (job?.builder_mode !== 'loop' || !job.activity?.length) return null
  const recent = job.activity.slice(-ACTIVITY_SHOWN)
  return (
    <ul aria-label="Build steps" className="mt-2 ml-[1.375rem] flex flex-col gap-1 border-l border-line pl-3 text-xs">
      {recent.map((text, i) => (
        <li key={job.activity.length - recent.length + i} className={i === recent.length - 1 ? 'text-fg' : 'text-dim'}>
          {text}
        </li>
      ))}
    </ul>
  )
}

export default function JobView({ jobId, onDone, onChange, feedbackBonus = 0, onBonus }) {
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [offline, setOffline] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  // Building and test planning run in parallel, so the stage can move back
  // and forth. Progress shows the furthest stage reached.
  const [reached, setReached] = useState(-1)

  async function handleCancel() {
    setCancelling(true)
    try {
      const next = await cancelJob(jobId)
      setJob(next)
      onDone?.(next)
    } catch (err) {
      // Usually the build finished first; the next poll shows how it ended.
      setError(err.message)
      setCancelling(false)
    }
  }

  useEffect(() => {
    let stopped = false
    let timer

    async function poll() {
      try {
        const next = await getJob(jobId)
        if (stopped) return
        setJob(next)
        setReached((r) => Math.max(r, STAGES.indexOf(next.stage)))
        setError('')
        setOffline(false)
        if (FINISHED.has(next.status)) {
          onDone?.(next)
          return
        }
      } catch (err) {
        if (stopped) return
        if (err.message === 'job not found') {
          setError('This build was lost because the server restarted. Please start it again.')
          onDone?.(null)
          return
        }
        if (err.unreachable) {
          // A dropped connection or a restarting server: keep the steps on
          // screen and try again on the next poll.
          setOffline(true)
        } else {
          setError(err.message)
        }
      }
      if (!stopped) timer = setTimeout(poll, POLL_MS)
    }

    poll()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [jobId, onDone])

  const finished = job && FINISHED.has(job.status)

  return (
    <section aria-label="Build progress" className="rounded-2xl border border-line bg-card p-6">
      <p role="status" className="sr-only">{announcement(job, reached, error, offline)}</p>
      <div className="flex items-center justify-between font-mono text-xs text-dim">
        <span>job {jobId}</span>
        <span className={job?.status === 'succeeded' ? 'text-accent' : ''}>{job?.status || 'starting'}</span>
      </div>

      {job?.status === 'queued' && (
        <p className="mt-4 text-sm text-muted">
          Waiting for a free builder. Vyskar builds two apps at a time, so yours starts as soon as
          one finishes.
        </p>
      )}

      {((!finished && !error && job?.status !== 'queued') || job?.status === 'succeeded') && (
        <BuildAnimation
          stage={reached}
          done={job?.status === 'succeeded'}
          shot={screenshotUrl(job)}
        />
      )}

      {!finished && !error && (
        <ol className="mt-5 flex flex-col gap-1 font-mono text-sm">
          {STAGES.map((stage, i) => {
            const done = i < reached
            const current = i === reached
            const time = job?.timings?.stages?.[stage]
            return (
              <li key={stage} className="py-1.5" aria-current={current ? 'step' : undefined}>
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden="true"
                    className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                      done ? 'bg-accent' : current ? 'animate-pulse bg-accent' : 'bg-pending'
                    }`}
                  />
                  <span className={`min-w-0 flex-1 ${done || current ? 'text-fg' : 'text-dim'}`}>{stage}</span>
                  {time && (
                    <span className={`tabular-nums text-xs ${time.running ? 'text-muted' : 'text-dim'}`}>
                      {formatDuration(time.seconds)}
                    </span>
                  )}
                </div>
                {stage === 'building' && <LoopActivity job={job} />}
              </li>
            )
          })}
        </ol>
      )}

      {!finished && !error && (
        <button
          type="button"
          onClick={handleCancel}
          disabled={cancelling}
          className="mt-5 min-h-11 rounded-full border border-wall px-5 text-sm text-muted hover:text-fg disabled:cursor-not-allowed disabled:opacity-50"
        >
          {cancelling ? 'Cancelling...' : 'Cancel build'}
        </button>
      )}

      {job?.status === 'cancelled' && (
        <div className="mt-5 flex flex-col gap-2">
          <p className="font-display text-xl font-bold">Build cancelled.</p>
          <p className="text-sm text-muted">Nothing was deployed. Change your prompt and build again.</p>
          {job.credit_refunded && (
            <p className="text-sm text-muted">It had not started yet, so your bought build was given back.</p>
          )}
        </div>
      )}

      {job?.status === 'succeeded' && (
        <div className="mt-5 flex flex-col gap-3">
          <p className="font-display text-xl font-bold">Your app is live.</p>
          <a href={job.deploy_url} target="_blank" rel="noreferrer" className="flex min-h-11 items-center self-start break-all font-mono text-accent">
            {job.deploy_url}
          </a>
          {job.trial && job.database_name && (
            <p className="text-sm text-muted">
              Free trial app: its saved data is deleted after 24 hours. Build it with your own AI key to keep it.
            </p>
          )}
          {job.confidence != null && (
            <p className={`font-mono text-sm ${job.confidence >= 95 ? 'text-green-400' : 'text-amber-400'}`}>
                Confidence {job.confidence}% ({job.test_summary?.split('\n')[0]})
            </p>
        )}
          <p className="text-sm text-muted">{job.test_summary}</p>
          {job.editable && onChange && (
            <button
              type="button"
              onClick={() => onChange(job.app_name)}
              className="mt-1 min-h-11 self-start rounded-full border border-accent px-5 text-sm font-semibold text-accent"
            >
              Change this app
            </button>
          )}
        </div>
      )}

      {(job?.status === 'failed' || job?.status === 'rejected') && (
        <div className="mt-5 flex flex-col gap-3">
          <p className="font-display text-xl font-bold">{failureHeading(job)}</p>
          <p className="text-sm leading-relaxed text-muted">
            {job.reason?.replace(/^(key rejected|no credit|paused): /, '')}
          </p>
          {job.credit_refunded && (
            <p className="text-sm text-muted">Your bought build was given back.</p>
          )}
          {job.test_summary && (
            <pre className="whitespace-pre-wrap rounded-lg bg-ink p-4 font-mono text-xs text-dim">{job.test_summary}</pre>
          )}
        </div>
      )}

      {finished && <StepTimes job={job} />}

      {(job?.status === 'succeeded' || job?.status === 'failed') && (
        <div className="mt-5 border-t border-line pt-5">
          <FeedbackForm jobId={jobId} bonus={feedbackBonus} onBonus={onBonus} />
        </div>
      )}

      {offline && !finished && !error && <p className="mt-4 text-sm text-muted">{OFFLINE_NOTE}</p>}

      {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
    </section>
  )
}
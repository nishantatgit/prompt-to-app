import { useEffect, useRef, useState } from 'react'
import { cancelJob, getJob } from '../lib/api.js'

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
export function formatDuration(seconds) {
  if (seconds == null) return ''
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`
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
  if (job.reason?.startsWith('key rejected')) return 'Your API key did not work.'
  if (job.reason?.startsWith('no credit')) return 'Your AI account is out of credit.'
  if (job.reason?.startsWith('internal error')) return 'Something went wrong on our side.'
  return 'The app did not pass its checks.'
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

export default function JobView({ jobId, onDone }) {
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const furthest = useRef(-1)

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
        setError('')
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
        setError(err.message)
      }
      if (!stopped) timer = setTimeout(poll, POLL_MS)
    }

    poll()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [jobId, onDone])

  // Building and test planning run in parallel, so the stage can move back and forth.
  // Progress shows the furthest stage reached.
  const index = STAGES.indexOf(job?.stage)
  if (index > furthest.current) furthest.current = index
  const reached = furthest.current
  const finished = job && FINISHED.has(job.status)

  return (
    <section aria-live="polite" className="rounded-2xl border border-line bg-card p-6">
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

      {!finished && !error && (
        <ol className="mt-5 flex flex-col gap-1 font-mono text-sm">
          {STAGES.map((stage, i) => {
            const done = i < reached
            const current = i === reached
            const time = job?.timings?.stages?.[stage]
            return (
              <li key={stage} className="py-1.5">
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
        </div>
      )}

      {job?.status === 'succeeded' && (
        <div className="mt-5 flex flex-col gap-3">
          <p className="font-display text-xl font-bold">Your app is live.</p>
          <a href={job.deploy_url} target="_blank" rel="noreferrer" className="break-all font-mono text-accent">
            {job.deploy_url}
          </a>
          {job.confidence != null && (
            <p className={`font-mono text-sm ${job.confidence >= 95 ? 'text-green-400' : 'text-amber-400'}`}>
                Confidence {job.confidence}% ({job.test_summary?.split('\n')[0]})
            </p>
        )}
          <p className="text-sm text-muted">{job.test_summary}</p>
        </div>
      )}

      {(job?.status === 'failed' || job?.status === 'rejected') && (
        <div className="mt-5 flex flex-col gap-3">
          <p className="font-display text-xl font-bold">{failureHeading(job)}</p>
          <p className="text-sm leading-relaxed text-muted">
            {job.reason?.replace(/^(key rejected|no credit): /, '')}
          </p>
          {job.test_summary && (
            <pre className="whitespace-pre-wrap rounded-lg bg-ink p-4 font-mono text-xs text-dim">{job.test_summary}</pre>
          )}
        </div>
      )}

      {finished && <StepTimes job={job} />}

      {error && <p className="mt-4 text-sm text-accent">{error}</p>}
    </section>
  )
}
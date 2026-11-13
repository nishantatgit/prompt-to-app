import { useEffect, useRef, useState } from 'react'
import { cancelJob, getJob } from '../lib/api.js'

const STAGES = [
  'checking request',
  'requirements',
  'architecture',
  'building',
  'planning tests',
  'testing',
  'deploying',
]
const POLL_MS = 2000
const FINISHED = new Set(['succeeded', 'failed', 'rejected', 'cancelled'])

function failureHeading(job) {
  if (job.status === 'rejected') return 'Vyskar could not build this request.'
  if (job.reason?.startsWith('key rejected')) return 'Your API key did not work.'
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

      {!finished && !error && (
        <ol className="mt-5 flex flex-col gap-1 font-mono text-sm">
          {STAGES.map((stage, i) => {
            const done = i < reached
            const current = i === reached
            return (
              <li key={stage} className="py-1.5">
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden="true"
                    className={`h-2.5 w-2.5 rounded-full ${
                      done ? 'bg-accent' : current ? 'animate-pulse bg-accent' : 'bg-pending'
                    }`}
                  />
                  <span className={done || current ? 'text-fg' : 'text-dim'}>{stage}</span>
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
            {job.reason?.replace(/^key rejected: /, '')}
          </p>
          {job.test_summary && (
            <pre className="whitespace-pre-wrap rounded-lg bg-ink p-4 font-mono text-xs text-dim">{job.test_summary}</pre>
          )}
        </div>
      )}

      {error && <p className="mt-4 text-sm text-accent">{error}</p>}
    </section>
  )
}
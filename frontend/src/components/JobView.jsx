import { useEffect, useRef, useState } from 'react'
import { getJob } from '../lib/api.js'

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
const FINISHED = new Set(['succeeded', 'failed', 'rejected'])

function failureHeading(job) {
  if (job.status === 'rejected') return 'Vyskar could not build this request.'
  if (job.reason?.startsWith('internal error')) return 'Something went wrong on our side.'
  return 'The app did not pass its checks.'
}

export default function JobView({ jobId, onDone }) {
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const furthest = useRef(-1)

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
        <span className={job?.status === 'succeeded' ? 'text-saffron' : ''}>{job?.status || 'starting'}</span>
      </div>

      {!finished && !error && (
        <ol className="mt-5 flex flex-col gap-1 font-mono text-sm">
          {STAGES.map((stage, i) => {
            const done = i < reached
            const current = i === reached
            return (
              <li key={stage} className="flex items-center gap-3 py-1.5">
                <span
                  aria-hidden="true"
                  className={`h-2.5 w-2.5 rounded-full ${
                    done ? 'bg-saffron' : current ? 'animate-pulse bg-saffron' : 'bg-pending'
                  }`}
                />
                <span className={done || current ? 'text-fg' : 'text-dim'}>{stage}</span>
              </li>
            )
          })}
        </ol>
      )}

      {job?.status === 'succeeded' && (
        <div className="mt-5 flex flex-col gap-3">
          <p className="font-display text-xl font-bold">Your app is live.</p>
          <a href={job.deploy_url} target="_blank" rel="noreferrer" className="break-all font-mono text-saffron">
            {job.deploy_url}
          </a>
          <p className="text-sm text-muted">{job.test_summary}</p>
        </div>
      )}

      {(job?.status === 'failed' || job?.status === 'rejected') && (
        <div className="mt-5 flex flex-col gap-3">
          <p className="font-display text-xl font-bold">{failureHeading(job)}</p>
          <p className="text-sm leading-relaxed text-muted">{job.reason}</p>
          {job.test_summary && (
            <pre className="whitespace-pre-wrap rounded-lg bg-ink p-4 font-mono text-xs text-dim">{job.test_summary}</pre>
          )}
        </div>
      )}

      {error && <p className="mt-4 text-sm text-saffron">{error}</p>}
    </section>
  )
}
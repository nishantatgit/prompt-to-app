import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../lib/api.js', () => ({
  getJob: vi.fn(),
  cancelJob: vi.fn(),
  screenshotUrl: () => '',
  sendFeedback: vi.fn(),
}))

import { getJob } from '../lib/api.js'
import JobView from './JobView.jsx'

// JobView polls every 2 seconds.
const RUNNING = {
  job_id: 'abc',
  status: 'running',
  stage: 'building',
  activity: [],
  timings: { stages: {}, total_seconds: 5 },
}

function unreachable() {
  return Object.assign(new Error("Can't reach Vyskar right now."), { unreachable: true })
}

async function nextPoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000)
  })
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('JobView polling', () => {
  it('keeps the steps on screen while Vyskar cannot be reached, then catches up', async () => {
    vi.useFakeTimers()
    getJob.mockResolvedValueOnce(RUNNING).mockRejectedValueOnce(unreachable()).mockResolvedValue(RUNNING)
    render(<JobView jobId="abc" />)
    await act(async () => {})
    expect(screen.getByRole('button', { name: 'Cancel build' })).toBeTruthy()

    await nextPoll()
    expect(screen.getAllByText(/Your build keeps going/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Cancel build' })).toBeTruthy()

    await nextPoll()
    expect(screen.queryAllByText(/Your build keeps going/)).toHaveLength(0)
  })

  it('still shows a real error in place of the steps', async () => {
    vi.useFakeTimers()
    getJob.mockResolvedValueOnce(RUNNING).mockRejectedValueOnce(new Error('Too many requests.'))
    render(<JobView jobId="abc" />)
    await act(async () => {})
    await nextPoll()
    expect(screen.getAllByText('Too many requests.').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Cancel build' })).toBeNull()
  })
})

describe('JobView cancelled', () => {
  it('says when a bought build was given back', async () => {
    getJob.mockResolvedValue({ ...RUNNING, status: 'cancelled', credit_refunded: true })
    render(<JobView jobId="abc" />)
    expect(await screen.findByText(/your bought build was given back/)).toBeTruthy()
  })

  it('says nothing about a refund otherwise', async () => {
    getJob.mockResolvedValue({ ...RUNNING, status: 'cancelled', credit_refunded: false })
    render(<JobView jobId="abc" />)
    await screen.findAllByText('Build cancelled.')
    expect(screen.queryByText(/given back/)).toBeNull()
  })
})

// Free and bought builds run on Vyskar's own AI key.
const STOPPED_BY_VYSKAR = {
  job_id: 'abc',
  status: 'failed',
  stage: 'building',
  activity: [],
  timings: { stages: {}, total_seconds: 30 },
  reason: "paused: This is on Vyskar's side, nothing for you to fix. Try again in a little while.",
}

describe('JobView when Vyskar\'s own AI key stops a build', () => {
  it('says it is on Vyskar, not the visitor, and that a bought build came back', async () => {
    getJob.mockResolvedValue({ ...STOPPED_BY_VYSKAR, credit_refunded: true })
    render(<JobView jobId="abc" />)
    await act(async () => {})
    expect(screen.getAllByText("Vyskar's AI stopped partway through.").length).toBeGreaterThan(0)
    expect(screen.getByText(/nothing for you to fix/)).toBeTruthy()
    expect(screen.queryByText(/paused:/)).toBeNull()
    expect(screen.queryByText(/out of credit/)).toBeNull()
    expect(screen.getByText('Your bought build was given back.')).toBeTruthy()
  })

  it('does not mention a bought build on a free one', async () => {
    getJob.mockResolvedValue({ ...STOPPED_BY_VYSKAR, trial: true, credit_refunded: false })
    render(<JobView jobId="abc" />)
    await act(async () => {})
    expect(screen.queryByText('Your bought build was given back.')).toBeNull()
  })
})

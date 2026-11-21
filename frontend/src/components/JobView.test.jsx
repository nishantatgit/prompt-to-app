import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../lib/api.js', () => ({
  getJob: vi.fn(),
  cancelJob: vi.fn(),
  screenshotUrl: () => '',
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

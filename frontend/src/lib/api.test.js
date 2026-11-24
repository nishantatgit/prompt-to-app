import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cancelJob,
  getJob,
  getQuestions,
  restoreBuilds,
  screenshotUrl,
  sendFeedback,
  startBuild,
} from './api.js'
import { SERVER_AWAY, UNREACHABLE } from './errors.js'
import { visitorId } from './visitor.js'

// A fetch Response with a JSON body, or with a body that is not JSON.
function reply(status, body) {
  const text = typeof body === 'string' ? body : JSON.stringify(body)
  return new Response(text, { status, headers: { 'Content-Type': 'application/json' } })
}

let fetchMock

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function lastRequest() {
  const [url, options = {}] = fetchMock.mock.calls.at(-1)
  return { url, options, body: options.body ? JSON.parse(options.body) : undefined }
}

describe('request errors', () => {
  it('returns the body of a successful reply', async () => {
    fetchMock.mockResolvedValue(reply(200, { job_id: 'j1', status: 'running' }))
    await expect(getJob('j1')).resolves.toEqual({ job_id: 'j1', status: 'running' })
  })

  it('says Vyskar cannot be reached when fetch fails, and marks it worth retrying', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const error = await getJob('j1').catch((e) => e)
    expect(error.message).toBe(UNREACHABLE)
    expect(error.unreachable).toBe(true)
  })

  it('passes an abort through unchanged, so callers can tell it from a lost connection', async () => {
    const abort = new DOMException('The operation was aborted.', 'AbortError')
    fetchMock.mockRejectedValue(abort)
    const error = await getJob('j1').catch((e) => e)
    expect(error).toBe(abort)
    expect(error.unreachable).toBeUndefined()
  })

  it("shows the server's own detail and does not mark it worth retrying", async () => {
    fetchMock.mockResolvedValue(reply(409, { detail: 'This build has already finished.' }))
    const error = await cancelJob('j1').catch((e) => e)
    expect(error.message).toBe('This build has already finished.')
    expect(error.unreachable).toBeUndefined()
  })

  it('treats a 503 with a detail as a refusal, not as the server being away', async () => {
    const busy = 'Vyskar is busy with other builds right now. Try again in a few minutes.'
    fetchMock.mockResolvedValue(reply(503, { detail: busy }))
    const error = await getJob('j1').catch((e) => e)
    expect(error.message).toBe(busy)
    expect(error.unreachable).toBeUndefined()
  })

  it.each([502, 503, 504])('marks a bare %i from the proxy as the server restarting', async (status) => {
    fetchMock.mockResolvedValue(reply(status, '<html>Bad gateway</html>'))
    const error = await getJob('j1').catch((e) => e)
    expect(error.message).toBe(SERVER_AWAY)
    expect(error.unreachable).toBe(true)
  })

  it('turns a validation error list into a readable sentence', async () => {
    fetchMock.mockResolvedValue(
      reply(422, { detail: [{ loc: ['body', 'payment_id'], type: 'string_pattern_mismatch' }] }),
    )
    const error = await restoreBuilds('order_123').catch((e) => e)
    expect(error.message).toMatch(/starts with pay_/)
  })

  it('names the status when an error has no body', async () => {
    fetchMock.mockResolvedValue(reply(500, ''))
    await expect(getJob('j1')).rejects.toThrow('Server returned 500')
  })
})

describe('startBuild', () => {
  it('sends the visitor id and blank optional fields as null', async () => {
    fetchMock.mockResolvedValue(reply(202, { job_id: 'j1', edit_key: 'k' }))
    await expect(startBuild({ prompt: 'A todo app', provider: 'anthropic' })).resolves.toEqual({
      job_id: 'j1',
      edit_key: 'k',
    })
    const { url, options, body } = lastRequest()
    expect(url).toBe('/api/build')
    expect(options.method).toBe('POST')
    expect(options.headers['X-Vyskar-Visitor']).toBe(visitorId())
    expect(body).toEqual({
      prompt: 'A todo app',
      provider: 'anthropic',
      api_key: null,
      app: null,
      edit_key: null,
      answers: [],
    })
  })

  it('refuses a reply without a job id', async () => {
    fetchMock.mockResolvedValue(reply(202, {}))
    await expect(startBuild({ prompt: 'x', provider: 'anthropic' })).rejects.toThrow(
      'The server did not return a job id.',
    )
  })
})

describe('paths and bodies', () => {
  it('escapes the job id in the URL', async () => {
    fetchMock.mockResolvedValue(reply(200, {}))
    await getJob('a/b?c')
    expect(lastRequest().url).toBe('/api/jobs/a%2Fb%3Fc')
  })

  it('sends feedback with missing fields as null or empty', async () => {
    fetchMock.mockResolvedValue(reply(200, { bonus_builds: 0 }))
    await sendFeedback({ message: 'Nice' })
    expect(lastRequest().body).toEqual({ job_id: null, rating: null, message: 'Nice', email: null })
  })

  it('builds the screenshot URL only when the job has one', () => {
    expect(screenshotUrl({ screenshot_url: '/api/jobs/j1/screenshot' })).toBe('/api/jobs/j1/screenshot')
    expect(screenshotUrl({})).toBe('')
    expect(screenshotUrl(null)).toBe('')
  })
})

describe('getQuestions', () => {
  const ask = { prompt: 'A shop', provider: 'anthropic' }

  it('returns the questions from the server', async () => {
    fetchMock.mockResolvedValue(reply(200, { questions: [{ question: 'Who buys?' }] }))
    await expect(getQuestions(ask)).resolves.toEqual([{ question: 'Who buys?' }])
  })

  it('returns no questions when the reply has none or is malformed', async () => {
    fetchMock.mockResolvedValue(reply(200, { questions: 'nope' }))
    await expect(getQuestions(ask)).resolves.toEqual([])
  })

  it('returns no questions on an error instead of holding up the build', async () => {
    fetchMock.mockResolvedValue(reply(500, { detail: 'boom' }))
    await expect(getQuestions(ask)).resolves.toEqual([])
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(getQuestions(ask)).resolves.toEqual([])
  })

  it('gives up after the timeout and returns no questions', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation(
      (_url, { signal }) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener('abort', () =>
            reject(new DOMException('The operation was aborted.', 'AbortError')),
          )
        }),
    )
    const questions = getQuestions(ask, 100)
    await vi.advanceTimersByTimeAsync(100)
    await expect(questions).resolves.toEqual([])
  })
})

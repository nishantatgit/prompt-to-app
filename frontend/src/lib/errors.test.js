import { describe, expect, it, vi } from 'vitest'
import { errorMessage } from './errors'
import { restoreBuilds, sendFeedback } from './api'

// The body FastAPI sends when RestoreRequest's pattern rejects payment_id.
const BAD_PAYMENT_ID = {
  detail: [
    {
      type: 'string_pattern_mismatch',
      loc: ['body', 'payment_id'],
      msg: "String should match pattern '^pay_[A-Za-z0-9]+$'",
      input: 'order_abc',
      ctx: { pattern: '^pay_[A-Za-z0-9]+$' },
    },
  ],
}

function respond(status, body) {
  return vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  })
}

describe('errorMessage', () => {
  it('passes a string detail through', () => {
    expect(errorMessage({ detail: 'Too many tries. Try again in an hour.' }, 429)).toBe(
      'Too many tries. Try again in an hour.',
    )
  })

  it('names the payment ID when it was rejected', () => {
    expect(errorMessage(BAD_PAYMENT_ID, 422)).toMatch(/starts with pay_/)
  })

  it('finds the field inside a nested location', () => {
    const body = { detail: [{ loc: ['body', 'answers', 0, 'answer'], msg: 'too long' }] }
    expect(errorMessage(body, 422)).toMatch(/answers/)
  })

  it('says something readable for a field it does not know', () => {
    const body = { detail: [{ loc: ['body', 'pack'], msg: 'Field required' }] }
    const text = errorMessage(body, 422)
    expect(text).not.toMatch(/object/)
    expect(text).toMatch(/wasn't accepted/)
  })

  it('falls back to the status when there is no detail', () => {
    expect(errorMessage({}, 502)).toBe('Server returned 502')
    expect(errorMessage(undefined, 500)).toBe('Server returned 500')
    expect(errorMessage({ detail: [] }, 422)).toBe('Server returned 422')
  })
})

describe('api requests', () => {
  it('never shows [object Object] for a rejected payment ID', async () => {
    vi.stubGlobal('fetch', respond(422, BAD_PAYMENT_ID))
    await expect(restoreBuilds('order_abc')).rejects.toThrow(/starts with pay_/)
    vi.unstubAllGlobals()
  })

  it('says the feedback message is too long', async () => {
    const body = { detail: [{ type: 'string_too_long', loc: ['body', 'message'], msg: 'too long' }] }
    vi.stubGlobal('fetch', respond(422, body))
    await expect(sendFeedback({ message: 'x' })).rejects.toThrow(/under 4000 characters/)
    vi.unstubAllGlobals()
  })

  it('keeps the server sentence for other errors', async () => {
    const body = { detail: 'No builds found for that payment ID. Check your Razorpay receipt.' }
    vi.stubGlobal('fetch', respond(404, body))
    await expect(restoreBuilds('pay_abc')).rejects.toThrow(/No builds found/)
    vi.unstubAllGlobals()
  })
})

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UNREACHABLE } from './errors'
import { NotAllowed, formatConfidence, formatCost, getFeedback, loadToken, saveToken, totalFor } from './admin'

beforeEach(() => sessionStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('formatConfidence', () => {
  it('shows the backend percentage as it is, not times 100', () => {
    expect(formatConfidence(100)).toBe('100%')
    expect(formatConfidence(87.5)).toBe('88%')
    expect(formatConfidence(0)).toBe('0%')
  })

  it('is empty when there is no number', () => {
    expect(formatConfidence(undefined)).toBe('')
    expect(formatConfidence(null)).toBe('')
    expect(formatConfidence(NaN)).toBe('')
  })
})

describe('formatCost', () => {
  it('shows cents for normal builds and more digits for tiny ones', () => {
    expect(formatCost(0.42)).toBe('$0.42')
    expect(formatCost(0.0031)).toBe('$0.0031')
    expect(formatCost(null)).toBe('')
  })
})

describe('admin token', () => {
  it('is kept in sessionStorage only', () => {
    saveToken('secret')
    expect(loadToken()).toBe('secret')
    expect(localStorage.getItem('vyskar-admin-token')).toBeNull()
    saveToken('')
    expect(loadToken()).toBe('')
  })
})

describe('getFeedback', () => {
  function reply(status, body) {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      status,
      ok: status < 400,
      json: async () => body,
    })
  }

  it('sorts entries newest first', async () => {
    reply(200, { feedback: [{ id: 1, created: 10 }, { id: 2, created: 30 }, { id: 3, created: 20 }] })
    const { rows } = await getFeedback('t')
    expect(rows.map((r) => r.id)).toEqual([2, 3, 1])
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer t')
  })

  it('puts the later of two entries from the same moment first', async () => {
    reply(200, { feedback: [{ id: 1, created: 10 }, { id: 2, created: 10 }] })
    const { rows } = await getFeedback('t')
    expect(rows.map((r) => r.id)).toEqual([2, 1])
  })

  it('passes on how many entries are stored in all', async () => {
    reply(200, {
      feedback: [{ id: 1, kind: 'waitlist', created: 1 }],
      totals: { feedback: 700, waitlist: 120 },
    })
    const { totals } = await getFeedback('t')
    expect(totals).toEqual({ feedback: 700, waitlist: 120 })
    expect(totalFor(totals, 'all')).toBe(820)
    expect(totalFor(totals, 'waitlist')).toBe(120)
  })

  it('counts the rows when the API sends no totals', async () => {
    reply(200, {
      feedback: [
        { id: 1, kind: 'waitlist', created: 1 },
        { id: 2, kind: 'feedback', created: 2 },
        { id: 3, kind: 'feedback', created: 3 },
      ],
    })
    const { totals } = await getFeedback('t')
    expect(totals).toEqual({ feedback: 2, waitlist: 1 })
  })

  it('throws NotAllowed for a rejected token', async () => {
    reply(401, { detail: 'no' })
    await expect(getFeedback('bad')).rejects.toBeInstanceOf(NotAllowed)
  })

  it('says Vyskar cannot be reached when the request never arrives', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(getFeedback('t')).rejects.toThrow(UNREACHABLE)
  })

  it('keeps the token when Vyskar cannot be reached', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Load failed'))
    await expect(getFeedback('t')).rejects.not.toBeInstanceOf(NotAllowed)
  })
})

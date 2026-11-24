import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { visitorId } from './visitor.js'

beforeEach(() => localStorage.clear())
afterEach(() => localStorage.clear())

describe('visitorId', () => {
  it('makes an id once and keeps it', () => {
    const first = visitorId()
    expect(first).toMatch(/\S{8,}/)
    expect(localStorage.getItem('vyskar.visitor')).toBe(first)
    expect(visitorId()).toBe(first)
  })

  it('keeps an id saved earlier', () => {
    localStorage.setItem('vyskar.visitor', 'saved-id')
    expect(visitorId()).toBe('saved-id')
  })

  it('still makes an id without crypto.randomUUID (older browsers, plain http)', () => {
    vi.stubGlobal('crypto', {})
    try {
      const id = visitorId()
      expect(id).toMatch(/^\d+-[a-z0-9]+$/)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('is empty when storage is blocked, so no free build is counted to a shared id', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(visitorId()).toBe('')
  })
})

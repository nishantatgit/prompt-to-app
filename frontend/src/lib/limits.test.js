import { describe, expect, it } from 'vitest'
import { serverLength } from './limits'

describe('serverLength', () => {
  it('counts plain and Hindi text like a string length', () => {
    expect(serverLength('hello')).toBe(5)
    expect(serverLength('नमस्ते')).toBe('नमस्ते'.length)
  })

  it('counts an emoji as one character, as the server does', () => {
    expect('👍'.length).toBe(2)
    expect(serverLength('👍')).toBe(1)
    expect(serverLength('👍'.repeat(10))).toBe(10)
  })
})

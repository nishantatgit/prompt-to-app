import { describe, expect, it } from 'vitest'
import { splitTestSummary } from './testSummary.js'

describe('splitTestSummary', () => {
  it('puts the count apart from the failed tests', () => {
    expect(splitTestSummary('7/8 tests passed.\nC3 failed: timeout\nRun error: boom')).toEqual({
      headline: '7/8 tests passed',
      details: ['C3 failed: timeout', 'Run error: boom'],
    })
  })

  it('has no details when every test passed', () => {
    expect(splitTestSummary('8/8 tests passed.')).toEqual({ headline: '8/8 tests passed', details: [] })
  })

  it('is empty for a missing summary', () => {
    expect(splitTestSummary('')).toEqual({ headline: '', details: [] })
    expect(splitTestSummary(null)).toEqual({ headline: '', details: [] })
    expect(splitTestSummary(undefined)).toEqual({ headline: '', details: [] })
  })

  it('drops blank lines', () => {
    expect(splitTestSummary('\n2/3 tests passed.\n\nC2 failed: x\n')).toEqual({
      headline: '2/3 tests passed',
      details: ['C2 failed: x'],
    })
  })
})

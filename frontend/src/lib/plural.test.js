import { describe, expect, it } from 'vitest'
import { builds } from './plural.js'

describe('builds', () => {
  it('says "build" for exactly one', () => {
    expect(builds(1)).toBe('1 build')
    expect(builds(1, 'free')).toBe('1 free build')
  })

  it('says "builds" for any other count', () => {
    expect(builds(0)).toBe('0 builds')
    expect(builds(2)).toBe('2 builds')
    expect(builds(5, 'more free')).toBe('5 more free builds')
  })
})

import { afterEach, describe, expect, it } from 'vitest'
import { jobFromSearch, takeJobFromUrl } from './openJob.js'

const ID = '26-11-23-1763900000-abc123def0'

describe('jobFromSearch', () => {
  it('reads the job id', () => {
    expect(jobFromSearch(`?job=${ID}`)).toBe(ID)
  })

  it('is null without one', () => {
    expect(jobFromSearch('')).toBeNull()
    expect(jobFromSearch('?job=')).toBeNull()
    expect(jobFromSearch(undefined)).toBeNull()
  })

  it('ignores anything that is not a job id', () => {
    expect(jobFromSearch('?job=../admin')).toBeNull()
    expect(jobFromSearch('?job=a%26b')).toBeNull()
    expect(jobFromSearch(`?job=${'a'.repeat(81)}`)).toBeNull()
  })
})

describe('takeJobFromUrl', () => {
  afterEach(() => window.history.replaceState(null, '', '/'))

  it('returns the job and takes it out of the address', () => {
    window.history.replaceState(null, '', `/?job=${ID}&ref=push#top`)
    expect(takeJobFromUrl()).toBe(ID)
    expect(window.location.search).toBe('?ref=push')
    expect(window.location.hash).toBe('#top')
  })

  it('leaves the address alone without a job', () => {
    window.history.replaceState(null, '', '/?ref=push')
    expect(takeJobFromUrl()).toBeNull()
    expect(window.location.search).toBe('?ref=push')
  })
})

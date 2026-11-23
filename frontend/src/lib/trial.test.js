import { describe, expect, it } from 'vitest'
import { nextFreeBuildsTime, pausedNote } from './trial.js'

describe('pausedNote', () => {
  it('points to adding a key when own keys are allowed', () => {
    expect(pausedNote(true)).toBe('Free builds are paused right now. Add your own AI key to build.')
  })

  it('never asks for a key when own keys are switched off', () => {
    expect(pausedNote(false)).not.toMatch(/key/i)
  })
})

describe('nextFreeBuildsTime', () => {
  it('is midnight UTC in the visitor\'s own time', () => {
    const now = new Date(Date.UTC(2026, 10, 23, 15, 0))
    expect(nextFreeBuildsTime(now, 'en-IN', 'Asia/Kolkata')).toMatch(/^5:30\s?am$/i)
    expect(nextFreeBuildsTime(now, 'en-US', 'UTC')).toMatch(/^12:00\sAM$/)
  })
})

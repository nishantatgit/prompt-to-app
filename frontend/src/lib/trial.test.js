import { describe, expect, it } from 'vitest'
import { pausedNote } from './trial.js'

describe('pausedNote', () => {
  it('points to adding a key when own keys are allowed', () => {
    expect(pausedNote(true)).toBe('Free builds are paused right now. Add your own AI key to build.')
  })

  it('never asks for a key when own keys are switched off', () => {
    expect(pausedNote(false)).not.toMatch(/key/i)
  })
})

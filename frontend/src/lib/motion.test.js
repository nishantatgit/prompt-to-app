import { describe, expect, it, vi } from 'vitest'
import { prefersReducedMotion, scrollBehavior } from './motion'

function mediaAnswers(reduce) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
    matches: reduce && query === '(prefers-reduced-motion: reduce)',
    media: query,
  }))
}

// jsdom has no matchMedia, so the tests give it one to spy on.
if (!window.matchMedia) window.matchMedia = () => ({ matches: false })

describe('prefersReducedMotion', () => {
  it('is true when the device asks for less motion', () => {
    mediaAnswers(true)
    expect(prefersReducedMotion()).toBe(true)
  })

  it('is false otherwise', () => {
    mediaAnswers(false)
    expect(prefersReducedMotion()).toBe(false)
  })

  it('is false when the browser cannot say', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(() => {
      throw new Error('not supported')
    })
    expect(prefersReducedMotion()).toBe(false)
  })
})

describe('scrollBehavior', () => {
  it('jumps when less motion is asked for', () => {
    mediaAnswers(true)
    expect(scrollBehavior()).toBe('auto')
  })

  it('glides otherwise', () => {
    mediaAnswers(false)
    expect(scrollBehavior()).toBe('smooth')
  })
})

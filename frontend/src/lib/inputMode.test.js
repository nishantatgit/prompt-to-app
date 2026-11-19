import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useInputMode, useIsPhone } from './inputMode'

const KEY = 'vyskar.inputMode'

// jsdom has no matchMedia: a fake one whose answer the test can change.
function fakeMatchMedia(matches) {
  const listeners = new Set()
  const query = {
    matches,
    addEventListener: (_, fn) => listeners.add(fn),
    removeEventListener: (_, fn) => listeners.delete(fn),
  }
  window.matchMedia = vi.fn(() => query)
  return {
    listeners,
    change(next) {
      query.matches = next
      listeners.forEach((fn) => fn())
    },
  }
}

beforeEach(() => localStorage.clear())

describe('useIsPhone', () => {
  it('asks for screens up to 639px wide', () => {
    fakeMatchMedia(true)
    renderHook(() => useIsPhone())
    expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 639px)')
  })

  it('follows the screen width as it changes', () => {
    const media = fakeMatchMedia(false)
    const { result } = renderHook(() => useIsPhone())
    expect(result.current).toBe(false)
    act(() => media.change(true))
    expect(result.current).toBe(true)
  })

  it('stops listening when unmounted', () => {
    const media = fakeMatchMedia(true)
    const { unmount } = renderHook(() => useIsPhone())
    expect(media.listeners.size).toBe(1)
    unmount()
    expect(media.listeners.size).toBe(0)
  })
})

describe('useInputMode', () => {
  it('starts on voice', () => {
    const { result } = renderHook(() => useInputMode())
    expect(result.current[0]).toBe('voice')
  })

  it('starts on the saved choice', () => {
    localStorage.setItem(KEY, 'text')
    const { result } = renderHook(() => useInputMode())
    expect(result.current[0]).toBe('text')
  })

  it('remembers a new choice on this device', () => {
    const { result } = renderHook(() => useInputMode())
    act(() => result.current[1]('text'))
    expect(result.current[0]).toBe('text')
    expect(localStorage.getItem(KEY)).toBe('text')
  })

  it('works without storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { result } = renderHook(() => useInputMode())
    expect(result.current[0]).toBe('voice')
    act(() => result.current[1]('text'))
    expect(result.current[0]).toBe('text')
  })
})

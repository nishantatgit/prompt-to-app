import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const KEY = 'vyskar.platform'

// platform.js checks once, when it is imported, so each test imports it fresh.
async function load({ search = '', referrer = '' } = {}) {
  window.history.replaceState(null, '', `/${search}`)
  vi.spyOn(document, 'referrer', 'get').mockReturnValue(referrer)
  vi.resetModules()
  return (await import('./platform')).inAndroidApp
}

beforeEach(() => sessionStorage.clear())
afterEach(() => window.history.replaceState(null, '', '/'))

describe('inAndroidApp', () => {
  it('is false in a normal browser', async () => {
    expect(await load()).toBe(false)
    expect(sessionStorage.getItem(KEY)).toBeNull()
  })

  it('is true when the Android app opens ?source=android, and remembers it', async () => {
    expect(await load({ search: '?source=android' })).toBe(true)
    expect(sessionStorage.getItem(KEY)).toBe('android')
  })

  it('is true when the referrer is the Android app', async () => {
    expect(await load({ referrer: 'android-app://com.vyskar.app/' })).toBe(true)
  })

  it('ignores other Android apps and other sources', async () => {
    expect(await load({ referrer: 'android-app://com.other.app/' })).toBe(false)
    expect(await load({ search: '?source=ios' })).toBe(false)
  })

  it('stays true on later pages of the session', async () => {
    sessionStorage.setItem(KEY, 'android')
    expect(await load()).toBe(true)
  })

  it('still detects the app when storage throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(await load({ search: '?source=android' })).toBe(true)
  })
})

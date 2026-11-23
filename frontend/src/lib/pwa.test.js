import { describe, expect, it } from 'vitest'
import { isIos } from './pwa'

const IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1'
const OLD_IPAD =
  'Mozilla/5.0 (iPad; CPU OS 12_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1 Mobile/15E148 Safari/604.1'
// Safari on iPadOS 13 and later, and on a Mac: the same desktop user agent.
const MAC_SAFARI =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15'
const ANDROID =
  'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'

describe('isIos', () => {
  it('knows an iPhone', () => {
    expect(isIos({ userAgent: IPHONE, maxTouchPoints: 5 })).toBe(true)
  })

  it('knows an iPad that still says iPad', () => {
    expect(isIos({ userAgent: OLD_IPAD, maxTouchPoints: 5 })).toBe(true)
  })

  it('knows an iPad that says it is a Mac, by its touch screen', () => {
    expect(isIos({ userAgent: MAC_SAFARI, maxTouchPoints: 5 })).toBe(true)
  })

  it('leaves a Mac alone', () => {
    expect(isIos({ userAgent: MAC_SAFARI, maxTouchPoints: 0 })).toBe(false)
    expect(isIos({ userAgent: MAC_SAFARI })).toBe(false)
  })

  it('leaves Android alone', () => {
    expect(isIos({ userAgent: ANDROID, maxTouchPoints: 5 })).toBe(false)
  })
})

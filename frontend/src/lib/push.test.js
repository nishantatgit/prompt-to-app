import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api.js', () => ({
  getPush: vi.fn(),
  watchJobWithPush: vi.fn(),
}))

import { getPush, watchJobWithPush } from './api.js'
import { keyBytes, resetPushKey, watchBuild } from './push.js'

// Any 65-byte P-256 public key shape works here: only the bytes matter.
const KEY = 'BAEC' + 'A'.repeat(83)

function fakeBrowser() {
  const subscription = {
    options: { applicationServerKey: keyBytes(KEY).buffer },
    toJSON: () => ({ endpoint: 'https://push.example/1' }),
    unsubscribe: vi.fn(),
  }
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(null),
    subscribe: vi.fn().mockResolvedValue(subscription),
  }
  vi.stubGlobal('PushManager', function PushManager() {})
  vi.stubGlobal('Notification', { permission: 'granted' })
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { getRegistration: vi.fn().mockResolvedValue({ pushManager }) },
  })
  return { pushManager, subscription }
}

beforeEach(() => {
  resetPushKey()
  vi.mocked(getPush).mockReset()
  vi.mocked(watchJobWithPush).mockReset().mockResolvedValue({})
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete navigator.serviceWorker
})

describe('keyBytes', () => {
  it('decodes base64url without padding', () => {
    expect(Array.from(keyBytes('-_8'))).toEqual([0xfb, 0xff])
  })

  it('decodes a full key to 65 bytes', () => {
    expect(keyBytes(KEY)).toHaveLength(65)
  })
})

describe('watchBuild', () => {
  it('subscribes and tells the server which job to push', async () => {
    const { pushManager } = fakeBrowser()
    vi.mocked(getPush).mockResolvedValue({ enabled: true, public_key: KEY })

    expect(await watchBuild('job-1')).toBe(true)
    expect(pushManager.subscribe).toHaveBeenCalledOnce()
    expect(watchJobWithPush).toHaveBeenCalledWith('job-1', { endpoint: 'https://push.example/1' })
  })

  it('does nothing when the server has push off, and does not ask again', async () => {
    fakeBrowser()
    vi.mocked(getPush).mockResolvedValue({ enabled: false, public_key: null })

    expect(await watchBuild('job-1')).toBe(false)
    expect(await watchBuild('job-2')).toBe(false)
    expect(getPush).toHaveBeenCalledOnce()
    expect(watchJobWithPush).not.toHaveBeenCalled()
  })

  it('asks the server again after it could not be reached', async () => {
    fakeBrowser()
    vi.mocked(getPush)
      .mockRejectedValueOnce(new Error('unreachable'))
      .mockResolvedValue({ enabled: true, public_key: KEY })

    expect(await watchBuild('job-1')).toBe(false)
    expect(await watchBuild('job-2')).toBe(true)
    expect(getPush).toHaveBeenCalledTimes(2)
    expect(watchJobWithPush).toHaveBeenCalledWith('job-2', expect.anything())
  })

  it('does nothing without notification permission', async () => {
    fakeBrowser()
    vi.stubGlobal('Notification', { permission: 'denied' })

    expect(await watchBuild('job-1')).toBe(false)
    expect(getPush).not.toHaveBeenCalled()
  })
})

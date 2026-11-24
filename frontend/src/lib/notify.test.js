import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askToNotify, buildMessage, notifyBuildDone } from './notify.js'

const LIVE = {
  job_id: 'job-1',
  status: 'succeeded',
  confidence: 100,
  deploy_url: 'https://todo-abc.vercel.app',
}

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
}

function stubNotification(permission) {
  const shown = []
  function FakeNotification(title, options) {
    shown.push({ title, options })
  }
  FakeNotification.permission = permission
  FakeNotification.requestPermission = vi.fn().mockResolvedValue('granted')
  vi.stubGlobal('Notification', FakeNotification)
  return { shown, FakeNotification }
}

function stubServiceWorker(registration) {
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { getRegistration: vi.fn().mockResolvedValue(registration) },
  })
}

beforeEach(() => setVisibility('hidden'))

afterEach(() => {
  vi.unstubAllGlobals()
  delete navigator.serviceWorker
  delete document.visibilityState
})

describe('buildMessage', () => {
  it('says a live app passed its tests and opens it', () => {
    expect(buildMessage(LIVE)).toEqual({
      title: 'Your app is live',
      body: 'Tests passed: 100%. Tap to open it.',
      url: 'https://todo-abc.vercel.app',
    })
  })

  it('keeps a part percentage as it is', () => {
    expect(buildMessage({ ...LIVE, confidence: 87.5 }).body).toBe('Tests passed: 87.5%. Tap to open it.')
  })

  it('says 0% rather than leaving the line out', () => {
    expect(buildMessage({ ...LIVE, confidence: 0 }).body).toBe('Tests passed: 0%. Tap to open it.')
  })

  it('leaves the percentage out when there were no tests', () => {
    expect(buildMessage({ ...LIVE, confidence: null }).body).toBe('Tap to open it.')
  })

  it('opens Vyskar when a live app has no address', () => {
    expect(buildMessage({ ...LIVE, deploy_url: null }).url).toBe('/')
  })

  it.each(['failed', 'rejected'])('says a %s build stopped', (status) => {
    expect(buildMessage({ job_id: 'job-1', status })).toEqual({
      title: 'Your build stopped',
      body: 'Tap to see what happened.',
      url: '/',
    })
  })

  it.each(['cancelled', 'running', 'queued', undefined])('says nothing for %s', (status) => {
    expect(buildMessage({ job_id: 'job-1', status })).toBeNull()
  })

  it('says nothing without a job', () => {
    expect(buildMessage(null)).toBeNull()
  })
})

describe('askToNotify', () => {
  it('asks when the browser has not been asked yet', async () => {
    const { FakeNotification } = stubNotification('default')
    await askToNotify()
    expect(FakeNotification.requestPermission).toHaveBeenCalledOnce()
  })

  it.each(['granted', 'denied'])('does not ask again once %s', async (permission) => {
    const { FakeNotification } = stubNotification(permission)
    await askToNotify()
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled()
  })

  it('does nothing in a browser without notifications', async () => {
    delete window.Notification
    await expect(askToNotify()).resolves.toBeUndefined()
  })
})

describe('notifyBuildDone', () => {
  it('shows it through the service worker, tagged with the job id', async () => {
    stubNotification('granted')
    const registration = { showNotification: vi.fn().mockResolvedValue(undefined) }
    stubServiceWorker(registration)
    await notifyBuildDone(LIVE)
    expect(registration.showNotification).toHaveBeenCalledWith('Your app is live', {
      body: 'Tests passed: 100%. Tap to open it.',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      // The same tag the server's Web Push uses, so a device shows one.
      tag: 'job-1',
      data: { url: 'https://todo-abc.vercel.app' },
    })
  })

  it('falls back to a page notification without a service worker', async () => {
    const { shown } = stubNotification('granted')
    stubServiceWorker(undefined)
    await notifyBuildDone(LIVE)
    expect(shown).toHaveLength(1)
    expect(shown[0].title).toBe('Your app is live')
  })

  it('stays quiet while Vyskar is on screen', async () => {
    const { shown } = stubNotification('granted')
    stubServiceWorker(undefined)
    setVisibility('visible')
    await notifyBuildDone(LIVE)
    expect(shown).toHaveLength(0)
  })

  it('stays quiet without permission', async () => {
    const { shown } = stubNotification('denied')
    stubServiceWorker(undefined)
    await notifyBuildDone(LIVE)
    expect(shown).toHaveLength(0)
  })

  it('stays quiet for a cancelled build', async () => {
    const { shown } = stubNotification('granted')
    stubServiceWorker(undefined)
    await notifyBuildDone({ job_id: 'job-1', status: 'cancelled' })
    expect(shown).toHaveLength(0)
  })

  it('does not throw when showing it fails', async () => {
    stubNotification('granted')
    stubServiceWorker({ showNotification: vi.fn().mockRejectedValue(new Error('no')) })
    await expect(notifyBuildDone(LIVE)).resolves.toBeUndefined()
  })
})

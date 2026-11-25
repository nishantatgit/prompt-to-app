import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// A stand-in for the browser's recognizer, so the tests never touch a mic.
class FakeRecognition {
  static last = null
  static failStart = false

  constructor() {
    this.started = false
    this.stopped = false
    this.aborted = false
    FakeRecognition.last = this
  }

  start() {
    if (FakeRecognition.failStart) throw new Error('InvalidStateError')
    this.started = true
  }

  stop() {
    this.stopped = true
    this.onend?.()
  }

  abort() {
    this.aborted = true
    this.onend?.()
  }
}

function results(...texts) {
  return { results: texts.map((text) => [{ transcript: text }]) }
}

// speech.js picks the recognizer when it is imported, so each test imports
// it again after setting one up.
async function load(recognition = FakeRecognition) {
  vi.resetModules()
  window.SpeechRecognition = recognition
  return import('./speech.js')
}

describe('speech', () => {
  beforeEach(() => {
    FakeRecognition.last = null
    FakeRecognition.failStart = false
  })

  afterEach(() => {
    delete window.SpeechRecognition
  })

  it('says whether the browser has a recognizer', async () => {
    expect((await load()).speechSupported()).toBe(true)
    expect((await load(null)).speechSupported()).toBe(false)
  })

  it('passes the whole transcript so far, tidied', async () => {
    const { listen } = await load()
    const onText = vi.fn()
    listen({ onText, lang: 'hi-IN' })
    const recognition = FakeRecognition.last
    expect(recognition.started).toBe(true)
    expect(recognition.lang).toBe('hi-IN')
    recognition.onresult(results(' a todo ', ' app  with   dates'))
    expect(onText).toHaveBeenLastCalledWith('a todo app with dates')
  })

  it('maps recognizer errors to plain messages and ignores aborted', async () => {
    const { listen } = await load()
    const onError = vi.fn()
    listen({ onText: vi.fn(), onError })
    const recognition = FakeRecognition.last
    recognition.onerror({ error: 'not-allowed' })
    expect(onError).toHaveBeenLastCalledWith('Allow microphone access for Vyskar to speak your app.')
    recognition.onerror({ error: 'something-new' })
    expect(onError).toHaveBeenLastCalledWith("Voice didn't work this time. Try again or type instead.")
    onError.mockClear()
    recognition.onerror({ error: 'aborted' })
    expect(onError).not.toHaveBeenCalled()
  })

  it('stop keeps listening to the end, so onEnd is called', async () => {
    const { listen } = await load()
    const onEnd = vi.fn()
    const session = listen({ onText: vi.fn(), onEnd })
    session.stop()
    expect(FakeRecognition.last.stopped).toBe(true)
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('cancel turns the mic off and calls nothing back afterwards', async () => {
    const { listen } = await load()
    const onText = vi.fn()
    const onEnd = vi.fn()
    const onError = vi.fn()
    const session = listen({ onText, onEnd, onError })
    const recognition = FakeRecognition.last
    session.cancel()
    expect(recognition.aborted).toBe(true)
    // A browser can still deliver a late result or error after abort.
    recognition.onresult?.(results('late words'))
    recognition.onerror?.({ error: 'network' })
    recognition.onend?.()
    expect(onText).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
    expect(onEnd).not.toHaveBeenCalled()
  })

  it('says so and ends when the recognizer will not start', async () => {
    FakeRecognition.failStart = true
    const { listen } = await load()
    const onEnd = vi.fn()
    const onError = vi.fn()
    const session = listen({ onText: vi.fn(), onEnd, onError })
    expect(onError).toHaveBeenCalledWith("Voice didn't work this time. Try again or type instead.")
    expect(onEnd).toHaveBeenCalledTimes(1)
    expect(() => session.stop()).not.toThrow()
    expect(() => session.cancel()).not.toThrow()
  })
})

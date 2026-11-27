import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// A stand-in for the Web Audio API: enough for tone() to schedule a sound.
function fakeAudioContext() {
  const param = () => ({ setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() })
  const made = []
  class FakeAudioContext {
    constructor() {
      this.state = 'running'
      this.currentTime = 0
      this.destination = {}
      this.resume = vi.fn(() => {
        this.state = 'running'
        return Promise.resolve()
      })
      made.push(this)
    }
    createOscillator() {
      const osc = { frequency: param(), connect: (node) => node, start: vi.fn(), stop: vi.fn() }
      this.oscillator = osc
      return osc
    }
    createGain() {
      return { gain: param(), connect: (node) => node }
    }
  }
  return { FakeAudioContext, made }
}

// feedback.js keeps one AudioContext for the page, so each test loads it fresh.
async function load() {
  vi.resetModules()
  return import('./feedback.js')
}

let fake

beforeEach(() => {
  fake = fakeAudioContext()
  vi.stubGlobal('AudioContext', fake.FakeAudioContext)
  navigator.vibrate = vi.fn()
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete navigator.vibrate
})

describe('voice cues', () => {
  it('buzz with their own patterns', async () => {
    const { startCue, stopCue, doneCue } = await load()
    startCue()
    expect(navigator.vibrate).toHaveBeenLastCalledWith(12)
    stopCue()
    expect(navigator.vibrate).toHaveBeenLastCalledWith([8, 40, 8])
    doneCue()
    expect(navigator.vibrate).toHaveBeenLastCalledWith(20)
  })

  it('play a tone, reusing one audio context', async () => {
    const { startCue, stopCue } = await load()
    startCue()
    stopCue()
    expect(fake.made).toHaveLength(1)
    expect(fake.made[0].oscillator.start).toHaveBeenCalled()
    expect(fake.made[0].resume).not.toHaveBeenCalled()
  })

  it('wake a suspended audio context so later cues are heard', async () => {
    const { startCue, stopCue } = await load()
    startCue()
    const context = fake.made[0]
    context.state = 'suspended' // such as after the phone went to the background
    stopCue()
    expect(context.resume).toHaveBeenCalledOnce()
    expect(context.state).toBe('running')
  })

  it('keep going when resuming is refused', async () => {
    const { startCue, stopCue } = await load()
    startCue()
    const context = fake.made[0]
    context.state = 'suspended'
    context.resume.mockReturnValue(Promise.reject(new Error('not allowed')))
    expect(() => stopCue()).not.toThrow()
    await Promise.resolve()
  })

  it('work without vibration or sound', async () => {
    delete navigator.vibrate
    vi.stubGlobal('AudioContext', undefined)
    const { startCue, stopCue, doneCue } = await load()
    expect(() => {
      startCue()
      stopCue()
      doneCue()
    }).not.toThrow()
  })
})

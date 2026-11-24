import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearSettings, loadSettings, saveSettings } from './settings.js'

const KEY = 'vyskar.settings'

beforeEach(() => localStorage.clear())
afterEach(() => localStorage.clear())

describe('loadSettings', () => {
  it('starts with Anthropic and no key', () => {
    expect(loadSettings()).toEqual({ provider: 'anthropic', apiKey: '' })
  })

  it('reads back what saveSettings wrote', () => {
    saveSettings({ provider: 'openai', apiKey: 'sk-test' })
    expect(loadSettings()).toEqual({ provider: 'openai', apiKey: 'sk-test' })
  })

  it('fills in a field that is missing', () => {
    localStorage.setItem(KEY, JSON.stringify({ apiKey: 'sk-ant-test' }))
    expect(loadSettings()).toEqual({ provider: 'anthropic', apiKey: 'sk-ant-test' })
  })

  it('drops a key that is not text, so the settings panel can trim it on save', () => {
    localStorage.setItem(KEY, JSON.stringify({ provider: 'openai', apiKey: null }))
    expect(loadSettings()).toEqual({ provider: 'openai', apiKey: '' })
  })

  it('drops a provider the app does not offer', () => {
    localStorage.setItem(KEY, JSON.stringify({ provider: 'gemini', apiKey: 'k' }))
    expect(loadSettings()).toEqual({ provider: 'anthropic', apiKey: 'k' })
  })

  it('ignores anything that is not a settings object', () => {
    for (const raw of ['"sk-ant-test"', '5', '[1,2]', 'true', '{not json']) {
      localStorage.setItem(KEY, raw)
      expect(loadSettings()).toEqual({ provider: 'anthropic', apiKey: '' })
    }
  })

  it('works when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(loadSettings()).toEqual({ provider: 'anthropic', apiKey: '' })
  })
})

describe('saveSettings and clearSettings', () => {
  it('clearSettings forgets the key', () => {
    saveSettings({ provider: 'openai', apiKey: 'sk-test' })
    clearSettings()
    expect(localStorage.getItem(KEY)).toBeNull()
    expect(loadSettings()).toEqual({ provider: 'anthropic', apiKey: '' })
  })

  it('does not throw when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(() => saveSettings({ provider: 'anthropic', apiKey: 'k' })).not.toThrow()
    expect(() => clearSettings()).not.toThrow()
  })
})

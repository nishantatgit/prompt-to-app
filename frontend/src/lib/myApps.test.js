import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { forgetApp, loadApps, rememberApp } from './myApps'

const KEY = 'vyskar.apps'

beforeEach(() => localStorage.clear())
afterEach(() => vi.useRealTimers())

describe('loadApps', () => {
  it('is empty when nothing is saved', () => {
    expect(loadApps()).toEqual([])
  })

  it('is empty when the saved list is not valid JSON', () => {
    localStorage.setItem(KEY, '{not json')
    expect(loadApps()).toEqual([])
  })

  it('is empty when the saved value is not a list', () => {
    localStorage.setItem(KEY, JSON.stringify({ name: 'todo' }))
    expect(loadApps()).toEqual([])
  })

  it('is empty when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(loadApps()).toEqual([])
  })
})

describe('rememberApp', () => {
  it('saves a new app with its key and prompt', () => {
    vi.useFakeTimers({ now: 1000 })
    const apps = rememberApp({ name: 'todo', url: 'https://todo.vercel.app', editKey: 'k1', prompt: 'a todo list' })
    const entry = { name: 'todo', url: 'https://todo.vercel.app', editKey: 'k1', prompt: 'a todo list', updatedAt: 1000 }
    expect(apps).toEqual([entry])
    expect(loadApps()).toEqual([entry])
  })

  it('puts the newest app first', () => {
    rememberApp({ name: 'one', url: 'u1', editKey: 'k1', prompt: 'p1' })
    rememberApp({ name: 'two', url: 'u2', editKey: 'k2', prompt: 'p2' })
    expect(loadApps().map((app) => app.name)).toEqual(['two', 'one'])
  })

  it('moves a changed app to the top and keeps its first prompt and its key', () => {
    rememberApp({ name: 'one', url: 'u1', editKey: 'k1', prompt: 'first prompt' })
    rememberApp({ name: 'two', url: 'u2', editKey: 'k2', prompt: 'p2' })
    const apps = rememberApp({ name: 'one', url: 'u1-new', prompt: 'add dark mode' })
    expect(apps).toHaveLength(2)
    expect(apps[0]).toMatchObject({ name: 'one', url: 'u1-new', editKey: 'k1', prompt: 'first prompt' })
  })

  it('takes a new key when one is given', () => {
    rememberApp({ name: 'one', url: 'u1', editKey: 'old', prompt: 'p' })
    expect(rememberApp({ name: 'one', url: 'u1', editKey: 'new' })[0].editKey).toBe('new')
  })

  it('keeps at most 50 apps, dropping the oldest', () => {
    for (let i = 0; i < 55; i++) rememberApp({ name: `app${i}`, url: `u${i}`, editKey: `k${i}`, prompt: 'p' })
    const apps = loadApps()
    expect(apps).toHaveLength(50)
    expect(apps[0].name).toBe('app54')
    expect(apps.at(-1).name).toBe('app5')
  })

  it('still returns the list when storage is full', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(rememberApp({ name: 'one', url: 'u1', editKey: 'k1', prompt: 'p' })).toHaveLength(1)
  })
})

describe('forgetApp', () => {
  it('removes only the named app', () => {
    rememberApp({ name: 'one', url: 'u1', editKey: 'k1', prompt: 'p' })
    rememberApp({ name: 'two', url: 'u2', editKey: 'k2', prompt: 'p' })
    expect(forgetApp('one').map((app) => app.name)).toEqual(['two'])
    expect(loadApps().map((app) => app.name)).toEqual(['two'])
  })

  it('does nothing for an unknown app', () => {
    rememberApp({ name: 'one', url: 'u1', editKey: 'k1', prompt: 'p' })
    expect(forgetApp('nope')).toHaveLength(1)
  })
})

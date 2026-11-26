import { describe, expect, it } from 'vitest'
import { failureText } from './failure'

describe('failureText', () => {
  it('puts a plain sentence before a requirements check failure', () => {
    const reason =
      "Requirements failed: requirement R1: source_quote 'bill amount' does not appear in the request.; Requirements failed: requirement R2: source_quote 'tip percent' does not appear in the request."
    const { text, detail } = failureText(reason)
    expect(text).toMatch(/couldn't work out exactly what the app should do/)
    expect(text).not.toMatch(/source_quote/)
    expect(detail).toBe(reason)
  })

  it.each([
    ['Architecture failed: table notes has no owner column', /couldn't plan how to put this app together/],
    ['Test planning failed: case T3 has no steps', /couldn't plan the tests/],
    ['A database migration failed: syntax error at or near "tabel"', /database didn't work/],
    ['build failed', /couldn't get the app to build/],
    ['stopped early', /couldn't get the app to build/],
  ])('rewords %s', (reason, plain) => {
    const { text, detail } = failureText(reason)
    expect(text).toMatch(plain)
    expect(detail).toBe(reason)
  })

  it('keeps reasons already written for people as they are', () => {
    const reason = 'No app called my-notes was found.'
    expect(failureText(reason)).toEqual({ text: reason, detail: '' })
  })

  it('drops the key problem prefix, as before', () => {
    expect(failureText('key rejected: Anthropic did not accept this key.')).toEqual({
      text: 'Anthropic did not accept this key.',
      detail: '',
    })
  })

  it('copes with no reason at all', () => {
    expect(failureText(undefined)).toEqual({ text: '', detail: '' })
  })
})

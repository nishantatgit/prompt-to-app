// Unit tests for the benchmark scorer. No Playwright run and no builds:
// results are written here in the shape of Playwright's JSON report.
//
//   yarn test:scripts

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { score } from './score.mjs'

const APPS = [
  { id: 3, slug: 'tip-calculator' },
  { id: 4, slug: 'pomodoro-timer' },
  { id: 11, slug: 'guestbook' },
]

// One spec as the JSON reporter writes it. The reporter drops the "@" from
// tags; the scorer reads them with or without it.
function spec(appId, title, status, { notDeployed = false, at = false } = {}) {
  const tag = `${at ? '@' : ''}app${String(appId).padStart(2, '0')}`
  return {
    title,
    tags: [tag, 'level1'],
    tests: [
      {
        status,
        annotations: notDeployed ? [{ type: 'skip', description: 'Not deployed yet' }] : [],
      },
    ],
  }
}

// Specs nested the way Playwright nests them: file, then describe.
function results(...specs) {
  return { suites: [{ title: 'apps.spec.ts', specs: [], suites: [{ title: 'app', specs }] }] }
}

function build(id, extra = {}) {
  return { id, status: 'succeeded', deploy_url: `https://app-${id}.vercel.app`, confidence: 100, ...extra }
}

function row(summary, id) {
  return summary.apps.find((a) => a.id === id)
}

test('an app passes when every test that ran passed', () => {
  const summary = score(
    results(spec(3, 'Page loads', 'expected'), spec(3, 'Splits the bill', 'expected')),
    [build(3)],
    APPS,
  )
  assert.equal(summary.score, '1/1')
  assert.deepEqual(row(summary, 3), {
    id: 3,
    slug: 'tip-calculator',
    result: 'pass',
    confidence: 100,
    broken_green: false,
    tests_passed: 2,
    tests_run: 2,
    failed: [],
    build_reason: undefined,
  })
})

test('one failed test fails the app and names the test', () => {
  const summary = score(
    results(spec(3, 'Page loads', 'expected'), spec(3, 'Splits the bill', 'unexpected')),
    [build(3, { confidence: 80 })],
    APPS,
  )
  const app = row(summary, 3)
  assert.equal(app.result, 'fail')
  assert.deepEqual(app.failed, ['Splits the bill'])
  assert.equal(app.tests_passed, 1)
  assert.equal(app.tests_run, 2)
  assert.equal(summary.score, '0/1')
})

test('a flaky test counts as failed', () => {
  const summary = score(results(spec(3, 'Timer counts down', 'flaky')), [build(3)], APPS)
  assert.equal(row(summary, 3).result, 'fail')
})

test('tests skipped inside a spec do not count against the app', () => {
  const summary = score(
    results(spec(3, 'Page loads', 'expected'), spec(3, 'Form has no email field', 'skipped')),
    [build(3)],
    APPS,
  )
  const app = row(summary, 3)
  assert.equal(app.result, 'pass')
  assert.equal(app.tests_run, 1)
})

test('an app whose build failed is not built, with the reason', () => {
  const summary = score(
    results(spec(4, 'Page loads', 'skipped', { notDeployed: true })),
    [build(4, { status: 'failed', deploy_url: '', confidence: null, reason: 'npm run build failed' })],
    APPS,
  )
  const app = row(summary, 4)
  assert.equal(app.result, 'not built')
  assert.equal(app.build_reason, 'npm run build failed')
  assert.equal(app.broken_green, false)
})

test('an app whose tests all skipped as not deployed is not built', () => {
  const summary = score(
    results(spec(4, 'Page loads', 'skipped', { notDeployed: true }), spec(4, 'Starts', 'skipped', { notDeployed: true })),
    [],
    APPS,
  )
  assert.equal(row(summary, 4).result, 'not built')
})

test('a deployed app with no tests in the run is "no tests ran", not "not built"', () => {
  // Playwright crashed before writing app 11's tests, or the grep missed it.
  const summary = score(results(spec(3, 'Page loads', 'expected')), [build(3), build(11)], APPS)
  const app = row(summary, 11)
  assert.equal(app.result, 'no tests ran')
  assert.equal(app.tests_run, 0)
  assert.equal(summary.score, '1/2')
})

test('a deployed app whose tests all skipped for other reasons is "no tests ran"', () => {
  const summary = score(results(spec(3, 'Form has no email field', 'skipped')), [build(3)], APPS)
  assert.equal(row(summary, 3).result, 'no tests ran')
})

test('a broken green is a failed app Vyskar scored 95% or more', () => {
  const summary = score(
    results(spec(3, 'Splits the bill', 'unexpected'), spec(4, 'Timer counts down', 'unexpected')),
    [build(3, { confidence: 95 }), build(4, { confidence: 94.9 })],
    APPS,
  )
  assert.equal(row(summary, 3).broken_green, true)
  assert.equal(row(summary, 4).broken_green, false)
  assert.equal(summary.broken_greens, 1)
})

test('a failed app with no confidence is not a broken green', () => {
  const summary = score(results(spec(3, 'Splits the bill', 'unexpected')), [build(3, { confidence: null })], APPS)
  assert.equal(row(summary, 3).broken_green, false)
})

test('without builds, the apps are the ones that have tests, read from tags with or without @', () => {
  const summary = score(
    results(
      spec(3, 'Page loads', 'expected', { at: true }),
      spec(11, 'Messages persist', 'expected'),
      { title: 'untagged helper check', tags: ['level1'], tests: [{ status: 'unexpected' }] },
    ),
    [],
    APPS,
  )
  assert.deepEqual(
    summary.apps.map((a) => [a.id, a.slug, a.result]),
    [
      [3, 'tip-calculator', 'pass'],
      [11, 'guestbook', 'pass'],
    ],
  )
  assert.equal(summary.score, '2/2')
})

test('apps are scored in build order, and an unknown app id gets slug "?"', () => {
  const summary = score(
    results(spec(11, 'Messages persist', 'expected'), spec(99, 'Page loads', 'expected'), spec(3, 'Page loads', 'expected')),
    [build(11), build(99), build(3)],
    APPS,
  )
  assert.deepEqual(
    summary.apps.map((a) => [a.id, a.slug]),
    [
      [11, 'guestbook'],
      [99, '?'],
      [3, 'tip-calculator'],
    ],
  )
})

test('an empty run scores 0/0', () => {
  assert.deepEqual(score({ suites: [] }, [], APPS), {
    score: '0/0',
    passed: 0,
    total: 0,
    broken_greens: 0,
    apps: [],
  })
})

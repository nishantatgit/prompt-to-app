// Turns a Playwright run into a benchmark score.
//
//   node scripts/score.mjs
//   node scripts/score.mjs results/latest/results.json results/latest/builds.json
//
// An app passes only when it was deployed and none of its tests failed,
// common or specific. Tests skipped inside a spec (for example "Form has no
// email field") do not count against it.
//
// A broken green is an app Vyskar scored 95% or more that the benchmark failed.
//
// Writes results/latest/score.json and prints a table.

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const GREEN = 95
const NOT_DEPLOYED = 'Not deployed yet'

function readJson(file, fallback) {
  const full = path.resolve(root, file)
  if (!fs.existsSync(full)) {
    if (fallback !== undefined) return fallback
    throw new Error(`${file} not found`)
  }
  return JSON.parse(fs.readFileSync(full, 'utf-8'))
}

// Every test in the run, with the app id taken from its @appNN tag.
function collectTests(suites, found = []) {
  for (const suite of suites ?? []) {
    for (const spec of suite.specs ?? []) {
      const tag = (spec.tags ?? []).find((t) => /^@?app\d+$/.test(t))
      if (!tag) continue
      const test = spec.tests[0] ?? {}
      found.push({
        appId: Number(tag.replace(/\D/g, '')),
        title: spec.title,
        status: test.status, // expected, unexpected, flaky or skipped
        notDeployed: (test.annotations ?? []).some((a) => a.description === NOT_DEPLOYED),
      })
    }
    collectTests(suite.suites, found)
  }
  return found
}

export function score(results, builds, apps) {
  const tests = collectTests(results.suites)
  const buildById = new Map(builds.map((b) => [b.id, b]))

  // Apps in this run: the ones built, or else every app that has tests.
  const ids = builds.length ? builds.map((b) => b.id) : [...new Set(tests.map((t) => t.appId))]

  const rows = ids.map((id) => {
    const app = apps.find((a) => a.id === id) ?? { slug: '?' }
    const build = buildById.get(id) ?? {}
    const own = tests.filter((t) => t.appId === id)
    const ran = own.filter((t) => t.status !== 'skipped')
    const failed = own.filter((t) => t.status === 'unexpected' || t.status === 'flaky')
    const deployed = (build.deploy_url ?? 'unknown') !== '' && !own.every((t) => t.notDeployed)

    let result = 'pass'
    if (!deployed) result = 'not built'
    else if (ran.length === 0) result = 'no tests ran'
    else if (failed.length) result = 'fail'

    const confidence = build.confidence ?? null
    return {
      id,
      slug: app.slug,
      result,
      confidence,
      broken_green: result !== 'pass' && confidence !== null && confidence >= GREEN,
      tests_passed: ran.length - failed.length,
      tests_run: ran.length,
      failed: failed.map((t) => t.title),
      build_reason: build.status && build.status !== 'succeeded' ? build.reason : undefined,
    }
  })

  const passed = rows.filter((r) => r.result === 'pass').length
  return {
    score: `${passed}/${rows.length}`,
    passed,
    total: rows.length,
    broken_greens: rows.filter((r) => r.broken_green).length,
    apps: rows,
  }
}

function main() {
  const [resultsFile = 'results/latest/results.json', buildsFile = 'results/latest/builds.json'] =
    process.argv.slice(2)
  const summary = score(readJson(resultsFile), readJson(buildsFile, []), readJson('apps.json'))

  const out = path.join(path.dirname(path.resolve(root, resultsFile)), 'score.json')
  fs.writeFileSync(out, JSON.stringify(summary, null, 2) + '\n')

  console.table(
    summary.apps.map(({ id, slug, result, confidence, tests_passed, tests_run, broken_green }) => ({
      id,
      slug,
      result,
      tests: `${tests_passed}/${tests_run}`,
      confidence,
      broken_green,
    })),
  )
  console.log(`Score: ${summary.score}   Broken greens: ${summary.broken_greens}`)
  for (const app of summary.apps.filter((a) => a.failed.length)) {
    console.log(`\n#${app.id} ${app.slug} failed:\n  - ${app.failed.join('\n  - ')}`)
  }
  console.log(`\nSaved ${path.relative(root, out)}`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main()
  } catch (error) {
    console.error(error.message)
    process.exit(1)
  }
}

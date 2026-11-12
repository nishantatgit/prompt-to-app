// One command for a whole benchmark run: build, test, score, save.
//
//   node scripts/benchmark.mjs --level 1 --label pipeline
//   node scripts/benchmark.mjs --ids 3,4 --label loop
//   node scripts/benchmark.mjs --retest path/to/builds.json --label pipeline-retest
//
// --retest skips building: it tests the apps already deployed in an earlier
// run, using that run's builds.json. It needs no API key and costs nothing,
// so specs can be fixed and the same apps scored again.
//
// Uses the same environment variables as build-apps.mjs (LLM_API_KEY,
// PROVIDER, VYSKAR_API). Saves everything to results/<label>-<date-time>/:
//   builds.json    job, status, confidence and time per app
//   results.json   Playwright's full results
//   score.json     pass, fail or not built per app, and the score
//   report/        Playwright's HTML report

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildAll, pickApps } from './build-apps.mjs'
import { score } from './score.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const latest = path.join(root, 'results', 'latest')

function flag(argv, name, fallback) {
  const i = argv.indexOf(name)
  return i === -1 ? fallback : argv[i + 1]
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf-8'))
}

// Reuse an earlier run's apps: point deployments.json at their URLs.
function reuseBuilds(file) {
  const builds = readJson(path.resolve(file))
  const deploymentsFile = path.join(root, 'deployments.json')
  const deployments = readJson(deploymentsFile)
  for (const b of builds) deployments[String(b.id)] = b.deploy_url ?? ''
  fs.writeFileSync(deploymentsFile, JSON.stringify(deployments, null, 2) + '\n')

  const ids = new Set(builds.map((b) => b.id))
  const apps = readJson(path.join(root, 'apps.json')).filter((a) => ids.has(a.id))
  console.log(`Retesting ${apps.length} apps from ${file}\n`)
  return { apps, builds }
}

function stamp() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`
}

// Run only the tests of the apps in this run, such as "@app03|@app04".
function runTests(apps) {
  const grep = apps.map((a) => `@app${String(a.id).padStart(2, '0')}`).join('|')
  console.log(`\nRunning tests: ${grep}\n`)
  // shell: true so "yarn" resolves to yarn.cmd on Windows. Playwright exits
  // with an error when tests fail, which is a normal result here.
  spawnSync(`yarn playwright test --grep "${grep}"`, { cwd: root, stdio: 'inherit', shell: true })

  const resultsFile = path.join(latest, 'results.json')
  if (!fs.existsSync(resultsFile)) throw new Error('Playwright did not write results/latest/results.json')
  return readJson(resultsFile)
}

async function main() {
  const argv = process.argv.slice(2)
  const label = flag(argv, '--label', 'run').replace(/[^\w-]/g, '-')
  const retest = flag(argv, '--retest')

  // Clear the last run so nothing old is scored by mistake.
  fs.rmSync(path.join(latest, 'results.json'), { force: true })

  let apps
  let builds
  if (retest) {
    ;({ apps, builds } = reuseBuilds(retest))
  } else {
    apps = pickApps(argv)
    builds = await buildAll(apps)
  }
  const results = runTests(apps)
  const summary = { label, ...score(results, builds, readJson(path.join(root, 'apps.json'))) }

  const out = path.join(root, 'results', `${label}-${stamp()}`)
  fs.mkdirSync(out, { recursive: true })
  fs.writeFileSync(path.join(out, 'builds.json'), JSON.stringify(builds, null, 2) + '\n')
  fs.copyFileSync(path.join(latest, 'results.json'), path.join(out, 'results.json'))
  fs.writeFileSync(path.join(out, 'score.json'), JSON.stringify(summary, null, 2) + '\n')
  const report = path.join(latest, 'report')
  if (fs.existsSync(report)) fs.cpSync(report, path.join(out, 'report'), { recursive: true })

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
  console.log(`${label}: ${summary.score}   Broken greens: ${summary.broken_greens}`)
  console.log(`Saved ${path.relative(root, out)}`)
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})

// Builds benchmark apps with Vyskar and records where each one was deployed.
//
//   node scripts/build-apps.mjs --level 1
//   node scripts/build-apps.mjs --ids 3,4
//
// Settings come from environment variables, so no key is ever written to disk:
//   LLM_API_KEY   your provider key (required)
//   PROVIDER      anthropic or openai (default anthropic)
//   VYSKAR_API    backend address (default http://localhost:8000)
//
// Writes:
//   deployments.json          the URL of each app built in this run
//   results/latest/builds.json   status, confidence and timing per app

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const API = (process.env.VYSKAR_API || 'http://localhost:8000').replace(/\/$/, '')
const PROVIDER = process.env.PROVIDER || 'anthropic'
const KEY = process.env.LLM_API_KEY
const POLL_MS = Number(process.env.POLL_MS || 10_000)
const FINISHED = new Set(['succeeded', 'failed', 'rejected'])

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.join(root, file), 'utf-8'))
}

function writeJson(file, data) {
  const full = path.join(root, file)
  fs.mkdirSync(path.dirname(full), { recursive: true })
  fs.writeFileSync(full, JSON.stringify(data, null, 2) + '\n')
}

export function pickApps(argv) {
  const apps = readJson('apps.json')
  const flag = (name) => {
    const i = argv.indexOf(name)
    return i === -1 ? undefined : argv[i + 1]
  }
  const level = flag('--level')
  const ids = flag('--ids')
  if (level) return apps.filter((a) => a.level === Number(level))
  if (ids) {
    const wanted = new Set(ids.split(',').map(Number))
    return apps.filter((a) => wanted.has(a.id))
  }
  throw new Error('Choose apps with --level N or --ids 1,2,3')
}

async function api(route, options) {
  const res = await fetch(`${API}${route}`, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `${route} returned ${res.status}`)
  return body
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function buildOne(app) {
  const started = Date.now()
  const { job_id } = await api('/api/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: app.prompt, provider: PROVIDER, api_key: KEY }),
  })
  console.log(`#${app.id} ${app.slug}: job ${job_id}`)

  let job
  let lastStage
  do {
    await sleep(POLL_MS)
    job = await api(`/api/jobs/${encodeURIComponent(job_id)}`)
    if (job.stage && job.stage !== lastStage) {
      console.log(`#${app.id} ${app.slug}: ${job.stage}`)
      lastStage = job.stage
    }
  } while (!FINISHED.has(job.status))

  return {
    id: app.id,
    slug: app.slug,
    job_id,
    status: job.status,
    reason: job.reason,
    deploy_url: job.deploy_url || '',
    confidence: job.confidence ?? null,
    database_name: job.database_name || '',
    seconds: Math.round((Date.now() - started) / 1000),
  }
}

// Build every app in order, then record the URLs. Returns one entry per app.
// afterEach(app, build) runs once each app is built, before the next starts.
export async function buildAll(apps, afterEach = async () => {}) {
  if (!KEY) throw new Error('Set LLM_API_KEY to your provider key first.')
  console.log(`Building ${apps.length} apps with ${PROVIDER} via ${API}\n`)

  const builds = []
  for (const app of apps) {
    try {
      builds.push(await buildOne(app))
    } catch (error) {
      builds.push({ id: app.id, slug: app.slug, status: 'error', reason: error.message, deploy_url: '' })
    }
    const last = builds.at(-1)
    console.log(`#${app.id} ${app.slug}: ${last.status} ${last.deploy_url || last.reason}\n`)
    const deployments = readJson('deployments.json')
    deployments[String(last.id)] = last.deploy_url
    writeJson('deployments.json', deployments)
    await afterEach(app, last)
  }

  // Keep other apps' URLs. An app that failed this run gets an empty URL, so
  // the tests skip it instead of testing an old deploy.
  const deployments = readJson('deployments.json')
  for (const b of builds) deployments[String(b.id)] = b.deploy_url
  writeJson('deployments.json', deployments)
  writeJson('results/latest/builds.json', builds)

  console.table(
    builds.map(({ id, slug, status, confidence, seconds }) => ({ id, slug, status, confidence, seconds })),
  )
  return builds
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  buildAll(pickApps(process.argv.slice(2))).catch((error) => {
    console.error(error.message)
    process.exit(1)
  })
}

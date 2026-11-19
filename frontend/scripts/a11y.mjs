// Accessibility check for the built frontend: runs axe on each screen at
// phone and desktop widths, and checks that every button, field and link
// that stands on its own is at least 44px tall and wide.
//
// Needs a build first: yarn build && yarn a11y
// The API is stubbed in the browser, so nothing reaches a real server.
// Exits with 1 when anything is found.
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, devices } from 'playwright'
import { AxeBuilder } from '@axe-core/playwright'

const DIST = fileURLToPath(new URL('../dist/', import.meta.url))
const MIN_TARGET = 44
const TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.json': 'application/json',
  '.webmanifest': 'application/manifest+json',
}

// A tiny static server for dist/, falling back to index.html.
function serve() {
  const server = createServer(async (req, res) => {
    const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname))
    let file = join(DIST, path)
    if (!file.startsWith(DIST)) file = join(DIST, 'index.html')
    let body
    try {
      body = await readFile(file)
    } catch {
      file = join(DIST, 'index.html')
      body = await readFile(file)
    }
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' })
    res.end(body)
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
}

const SAVED_APP = {
  name: 'tip-calculator-7f3a',
  url: 'https://tip-calculator-7f3a.vercel.app',
  editKey: 'key',
  prompt: 'A tip calculator: bill amount, tip percent, number of people',
  updatedAt: Date.now(),
}

const RUNNING_JOB = {
  job_id: 'job123',
  status: 'running',
  stage: 'building',
  timings: { stages: { 'checking request': { seconds: 3 }, requirements: { seconds: 20 }, building: { seconds: 40, running: true } } },
}

const DONE_JOB = {
  job_id: 'job123',
  status: 'succeeded',
  stage: 'deploying',
  app_name: SAVED_APP.name,
  deploy_url: SAVED_APP.url,
  editable: true,
  confidence: 96,
  test_summary: '24 of 25 checks passed',
  timings: { total_seconds: 190, stages: { requirements: { seconds: 20 }, building: { seconds: 100 } } },
  usage: { complete: true, cost_usd: 0.42 },
}

// Each screen: the stubbed API answers, and the steps that bring it up.
const SCREENS = [
  {
    name: 'home',
    api: { trial: { enabled: true, builds_left: 2 } },
  },
  {
    name: 'home, typing',
    mode: 'type',
    api: { trial: { enabled: true, builds_left: 2 } },
  },
  {
    name: 'builds used up (dialog)',
    api: {
      trial: { enabled: true, builds_left: 0, bonus_available: true, bonus_builds: 2 },
      credits: { enabled: true, builds_left: 0, packs: [{ id: 'p5', builds: 5, price_inr: 199 }, { id: 'p20', builds: 20, price_inr: 599 }] },
    },
    async open(page) {
      await page.getByRole('dialog').waitFor()
    },
  },
  {
    name: 'waitlist and own key (dialog)',
    api: { trial: { enabled: true, builds_left: 0 } },
    async open(page) {
      await page.getByRole('dialog').waitFor()
    },
  },
  {
    name: 'questions',
    mode: 'type',
    api: {
      trial: { enabled: true, builds_left: 2 },
      clarify: { questions: [{ question: 'Who uses it?', options: ['Just me', 'My team'] }] },
    },
    async open(page) {
      await page.getByLabel('Describe your app').fill('A to-do list')
      await page.getByRole('button', { name: 'Build my app' }).click()
      await page.getByRole('heading', { name: 'One quick question' }).waitFor()
    },
  },
  {
    name: 'building',
    mode: 'type',
    api: { trial: { enabled: true, builds_left: 2 }, job: RUNNING_JOB },
    async open(page) {
      await page.getByLabel('Describe your app').fill('A to-do list')
      await page.getByRole('button', { name: 'Build my app' }).click()
      await page.getByRole('button', { name: 'Cancel build' }).waitFor()
    },
  },
  {
    name: 'build finished',
    mode: 'type',
    api: { trial: { enabled: true, builds_left: 2 }, job: DONE_JOB },
    async open(page) {
      await page.getByLabel('Describe your app').fill('A to-do list')
      await page.getByRole('button', { name: 'Build my app' }).click()
      await page.getByText('Your app is live.').last().waitFor()
    },
  },
  {
    name: 'build failed, feedback open',
    mode: 'type',
    api: {
      trial: { enabled: true, builds_left: 2 },
      job: { ...DONE_JOB, status: 'failed', reason: 'tests failed', test_summary: '3 of 25 checks failed' },
    },
    async open(page) {
      await page.getByLabel('Describe your app').fill('A to-do list')
      await page.getByRole('button', { name: 'Build my app' }).click()
      await page.getByRole('button', { name: 'Not right' }).click()
      await page.getByLabel('Your feedback').waitFor()
    },
  },
  {
    name: 'changing an app',
    mode: 'type',
    api: { trial: { enabled: true, builds_left: 2 } },
    async open(page) {
      await page.getByRole('button', { name: 'Change', exact: true }).click()
      await page.getByRole('heading', { name: 'What should change?' }).waitFor()
    },
  },
  {
    name: 'own key saved (dialog)',
    key: true,
    api: { trial: { enabled: false, builds_left: 0 } },
    async open(page) {
      await page.getByRole('button', { name: /key saved/i }).click()
      await page.getByRole('dialog').waitFor()
    },
  },
]

function stubApi(page, api) {
  const answers = {
    '/api/trial': api.trial ?? { enabled: false, builds_left: 0 },
    '/api/credits': api.credits ?? { enabled: false, builds_left: 0, packs: [] },
    '/api/voice': { enabled: true },
    '/api/clarify': api.clarify ?? { questions: [] },
    '/api/build': { job_id: 'job123', edit_key: 'key' },
    '/api/push': { enabled: false },
  }
  return page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname
    const body = path.startsWith('/api/jobs/') ? api.job ?? RUNNING_JOB : answers[path] ?? {}
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
}

// Buttons, fields and links smaller than 44px, except links inside a
// sentence (WCAG 2.5.8's inline exception).
async function smallTargets(page) {
  return page.evaluate((min) => {
    const found = []
    const selector = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [tabindex]:not([tabindex="-1"])'
    for (const el of document.querySelectorAll(selector)) {
      const box = el.getBoundingClientRect()
      const style = getComputedStyle(el)
      if (!box.width || !box.height || style.visibility === 'hidden') continue
      if (el.closest('[aria-hidden="true"], [inert]')) continue
      if (el.matches('a') && el.closest('p, li') && style.display === 'inline') continue
      if (box.width < min - 0.5 || box.height < min - 0.5) {
        const label = (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || el.tagName).trim().slice(0, 60)
        found.push(`${el.tagName.toLowerCase()} "${label}" is ${Math.round(box.width)}x${Math.round(box.height)}`)
      }
    }
    return found
  }, MIN_TARGET)
}

const SIZES = [
  { name: 'phone', options: { ...devices['iPhone 13'] } },
  { name: 'desktop', options: { viewport: { width: 1280, height: 800 } } },
]

const server = await serve()
const base = `http://127.0.0.1:${server.address().port}/`
const browser = await chromium.launch()
let problems = 0

for (const size of SIZES) {
  for (const screen of SCREENS) {
    const context = await browser.newContext({ ...size.options, reducedMotion: 'reduce', serviceWorkers: 'block' })
    await context.addInitScript(
      ([apps, mode, key]) => {
        localStorage.setItem('vyskar.apps', JSON.stringify(apps))
        if (mode) localStorage.setItem('vyskar.inputMode', mode)
        if (key) localStorage.setItem('vyskar.settings', JSON.stringify({ provider: 'anthropic', apiKey: 'sk-ant-test' }))
      },
      [[SAVED_APP], screen.mode ?? null, Boolean(screen.key)],
    )
    const page = await context.newPage()
    await stubApi(page, screen.api)
    // Fonts and analytics come from other sites; the check runs offline.
    await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => route.abort())
    await page.goto(base)
    await page.locator('main').waitFor()
    await page.waitForTimeout(300)
    if (screen.open) await screen.open(page)
    await page.waitForTimeout(300)

    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze()
    const small = await smallTargets(page)
    const where = `${screen.name} @ ${size.name}`
    if (!result.violations.length && !small.length) {
      console.log(`ok    ${where}`)
    } else {
      console.log(`FAIL  ${where}`)
      for (const v of result.violations) {
        problems++
        console.log(`  axe ${v.id} (${v.impact}): ${v.help}`)
        for (const node of v.nodes.slice(0, 5)) console.log(`      ${node.target.join(' ')}  ${node.failureSummary?.split('\n')[1]?.trim() ?? ''}`)
      }
      for (const s of small) {
        problems++
        console.log(`  tap target under ${MIN_TARGET}px: ${s}`)
      }
    }
    await context.close()
  }
}

await browser.close()
server.close()
if (problems) {
  console.log(`\n${problems} problem(s) found.`)
  process.exit(1)
}
console.log('\nNo problems found.')

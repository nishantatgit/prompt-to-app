import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: a big MM:SS countdown from a fixed starting time that the user
// can start, pause and reset. Start works only when stopped or paused, Pause
// only while running. The time never goes below 00:00; when a session ends the
// timer may stop at 00:00 or move on to a break, as the Pomodoro technique does.
// The prompt does not ask for setting the length, so that is not checked.
//
// The browser clock is faked, so "run 25 minutes" takes milliseconds.
// A control that should do nothing passes if it is hidden, disabled, or
// clicking it changes nothing. A single Start/Pause toggle button works too.

const app = getApp(4)
const url = getAppUrl(app.id)

const START = /start|play|resume/i
const PAUSE = /pause/i
const RESET = /reset|restart/i

// The element whose whole text is a time like 25:00.
function timerDisplay(page: Page): Locator {
  return page.getByText(/^\s*-?\s*\d{1,3}\s*:\s*\d{2}\s*$/).first()
}

async function readSeconds(page: Page): Promise<number> {
  const text = await timerDisplay(page).innerText()
  const negative = /-/.test(text)
  const [m, s] = text.replace(/[^\d:]/g, '').split(':').map(Number)
  return (negative ? -1 : 1) * (m * 60 + s)
}

function button(page: Page, name: RegExp): Locator {
  return page.getByRole('button', { name }).first()
}

async function isUnavailable(control: Locator): Promise<boolean> {
  if ((await control.count()) === 0) return true
  if (!(await control.isVisible())) return true
  return control.isDisabled()
}

// Click a control that should do nothing right now. Passes if it is hidden or
// disabled. Otherwise it is clicked, and the caller checks nothing changed.
async function clickIfAvailable(control: Locator) {
  if (!(await isUnavailable(control))) await control.click()
}

// Seconds may be off by one, since the app's ticks and the test's reads
// do not line up exactly.
async function expectSeconds(page: Page, expected: number) {
  const actual = await readSeconds(page)
  expect(Math.abs(actual - expected)).toBeLessThanOrEqual(1)
}



test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.clock.install()
    await page.goto(url!)
  })

  test('shows a timer that starts above zero', async ({ page }) => {
    await expect(timerDisplay(page)).toBeVisible()
    expect(await readSeconds(page)).toBeGreaterThan(0)
  })

  test('timer is big and in the first screen', async ({ page }) => {
    const { fontSize, top, fold } = await timerDisplay(page).evaluate((el) => {
      const sizes = [el, ...el.querySelectorAll('*')].map((e) =>
        parseFloat(getComputedStyle(e).fontSize),
      )
      return {
        fontSize: Math.max(...sizes),
        top: el.getBoundingClientRect().top,
        fold: window.innerHeight,
      }
    })
    expect(fontSize).toBeGreaterThanOrEqual(48)
    expect(top).toBeLessThan(fold)
  })

  test('start counts down', async ({ page }) => {
    const full = await readSeconds(page)
    await button(page, START).click()
    await page.clock.runFor(3_000)
    await expectSeconds(page, full - 3)
  })

  test('start does nothing while running', async ({ page }) => {
    const full = await readSeconds(page)
    await button(page, START).click()
    await page.clock.runFor(2_000)

    await clickIfAvailable(button(page, START))
    await page.clock.runFor(2_000)
    await expectSeconds(page, full - 4)
  })

  test('pause does nothing before start', async ({ page }) => {
    const full = await readSeconds(page)
    await clickIfAvailable(button(page, PAUSE))
    await page.clock.runFor(3_000)
    await expectSeconds(page, full)
  })

  test('pause stops the countdown and start resumes it', async ({ page }) => {
    const full = await readSeconds(page)
    await button(page, START).click()
    await page.clock.runFor(3_000)

    await button(page, PAUSE).click()
    const paused = await readSeconds(page)
    await page.clock.runFor(5_000)
    await expectSeconds(page, paused)

    await button(page, START).click()
    await page.clock.runFor(2_000)
    await expectSeconds(page, paused - 2)
    expect(paused).toBeLessThan(full)
  })

  test('reset returns to the full time and stops', async ({ page }) => {
    const full = await readSeconds(page)
    await button(page, START).click()
    await page.clock.runFor(5_000)

    await button(page, RESET).click()
    await expectSeconds(page, full)
    await page.clock.runFor(3_000)
    await expectSeconds(page, full)
  })

  test('a reload starts a new session from the full time', async ({ page }) => {
    const full = await readSeconds(page)
    await button(page, START).click()
    await page.clock.runFor(10_000)

    await page.reload()
    await expectSeconds(page, full)
  })

  test('never goes below zero when the session ends', async ({ page }) => {
    const full = await readSeconds(page)
    await button(page, START).click()
    await page.clock.runFor((full + 5) * 1_000)

    const after = await readSeconds(page)
    expect(after).toBeGreaterThanOrEqual(0)

    // Stopped at 00:00: Pause must do nothing. Moved on to a break: the break
    // is a new countdown, so there is nothing more to check.
    if (after === 0) {
      await clickIfAvailable(button(page, PAUSE))
      await page.clock.runFor(3_000)
      expect(await readSeconds(page)).toBe(0)
    }
  })


})
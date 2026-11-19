import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: five questions, one at a time or all on one page; answering
// all of them shows a score out of 5.

const app = getApp(8)
const url = getAppUrl(app.id)

const NAV = /^(next|submit|finish|check|continue|see (my )?(score|results?)|done|start)/i
const SCORE = /\b([0-5])\s*(\/|out of|of)\s*5\b/i

// The answer choices on screen: radios, or buttons that are not navigation.
async function choices(page: Page): Promise<Locator[]> {
  const radios = await page.getByRole('radio').all()
  if (radios.length) return radios
  const buttons = await page.getByRole('button').all()
  const out: Locator[] = []
  for (const b of buttons) {
    const name = ((await b.getAttribute('aria-label')) || (await b.innerText())).trim()
    if (name && !NAV.test(name) && !/restart|again|reset|retake/i.test(name)) out.push(b)
  }
  return out
}

// A score such as "3/5" or "You got 3 out of 5", on a line that is not a
// question counter like "Question 5 of 5".
async function finished(page: Page) {
  const lines = (await page.locator('body').innerText()).split('\n')
  return lines.some((line) => SCORE.test(line) && !/question/i.test(line))
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('answering every question shows a score out of 5', async ({ page }) => {
    const start = page.getByRole('button', { name: /^start/i })
    if ((await start.count()) > 0) await start.first().click()

    // One question at a time: answer, then go on. All on one page: each
    // radio group gets its first option. At most 12 rounds.
    for (let round = 0; round < 12 && !(await finished(page)); round++) {
      const radios = page.getByRole('radio')
      if ((await radios.count()) >= 10) {
        const names = new Set<string>()
        for (const r of await radios.all()) {
          const group = (await r.getAttribute('name')) ?? ''
          if (!names.has(group)) {
            names.add(group)
            await r.check()
          }
        }
      } else {
        const options = await choices(page)
        if (options.length) await options[0].click()
      }
      const go = page.getByRole('button', { name: NAV })
      if ((await go.count()) > 0 && (await go.first().isEnabled())) await go.first().click()
      await page.waitForTimeout(300)
    }

    await expect.poll(() => finished(page), { message: 'a score such as 3/5 is shown' }).toBe(true)
  })

  test('there are five questions', async ({ page }) => {
    const text = await page.locator('body').innerText()
    const counter = /\b(question\s*)?1\s*(\/|of|out of)\s*5\b/i.test(text)
    const allOnPage = (await page.getByRole('radiogroup').count()) === 5 ||
      new Set(await Promise.all((await page.getByRole('radio').all()).map((r) => r.getAttribute('name')))).size === 5
    expect(counter || allOnPage, 'shows "1 of 5", or five questions on the page').toBe(true)
  })
})

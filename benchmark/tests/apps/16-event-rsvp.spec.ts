import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { asAnotherVisitor, button, field, fillIfPresent, unique, uniqueEmail } from '../../helpers/storage'

// Pass check: a guest RSVPs and the count of guests or spots left changes;
// once the limit is reached, more RSVPs are refused; the count is saved on a
// server, so a second browser sees the same.
//
// The count is read from text such as "12 of 50", "12/50", "38 spots left"
// or "Guests: 12". Filling the event up is only tried when at most 30 spots
// are left, so a limit of 500 is not RSVPed to the end.

const app = getApp(16)
const url = getAppUrl(app.id)

const NAME = /name/i
const EMAIL = /e-?mail/i
const RSVP = /rsvp|attend|join|register|reserve|count me in|i('|’)?m (in|going)|yes|confirm|book/i
const FULL = /full|no (more )?(spots|seats|places)|sold out|limit (has been |is )?reached|waitlist/i
const MAX_FILL = 30

type Count = { taken?: number; limit?: number; left?: number }

async function readCount(page: Page): Promise<Count> {
  const text = (await page.locator('body').innerText()).replace(/,/g, '')
  const ofLimit = text.match(/(\d+)\s*(?:\/|of|out of)\s*(\d+)/i)
  const left = text.match(/(\d+)\s*(?:spots?|seats?|places?|tickets?)?\s*(?:left|remaining|available)/i)
  return {
    taken: ofLimit ? Number(ofLimit[1]) : undefined,
    limit: ofLimit ? Number(ofLimit[2]) : undefined,
    left: left ? Number(left[1]) : ofLimit ? Number(ofLimit[2]) - Number(ofLimit[1]) : undefined,
  }
}

async function rsvp(page: Page) {
  await field(page, NAME).fill(unique('Guest'))
  await fillIfPresent(page, EMAIL, uniqueEmail())
  await button(page, RSVP).click()
}

function changed(before: Count, after: Count): boolean {
  if (before.left !== undefined && after.left !== undefined) return after.left === before.left - 1
  if (before.taken !== undefined && after.taken !== undefined) return after.taken === before.taken + 1
  return false
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
    await page.waitForLoadState('networkidle')
  })

  test('shows how many spots are taken or left', async ({ page }) => {
    const count = await readCount(page)
    expect(count.left ?? count.taken, 'a guest count or spots left is shown').toBeDefined()
  })

  test('an RSVP changes the count by one', async ({ page }) => {
    const before = await readCount(page)
    test.skip((before.left ?? 1) === 0, 'The event is already full')
    await rsvp(page)
    await expect.poll(async () => changed(before, await readCount(page)), { timeout: 10_000 }).toBe(true)
  })

  test('another browser sees the same count', async ({ page, browser }) => {
    const before = await readCount(page)
    test.skip((before.left ?? 1) === 0, 'The event is already full')
    await rsvp(page)
    await expect.poll(async () => changed(before, await readCount(page)), { timeout: 10_000 }).toBe(true)
    const after = await readCount(page)

    await asAnotherVisitor(browser, url!, async (visitor) => {
      await visitor.waitForLoadState('networkidle')
      await expect.poll(async () => (await readCount(visitor)).left ?? (await readCount(visitor)).taken, {
        timeout: 10_000,
      }).toBe(after.left ?? after.taken)
    })
  })

  test('once the limit is reached, more RSVPs are refused', async ({ page }) => {
    test.setTimeout(180_000)
    let count = await readCount(page)
    test.skip(count.left === undefined, 'Spots left cannot be read from the page')
    test.skip(count.left! > MAX_FILL, `More than ${MAX_FILL} spots left; not filled to the end`)

    while (count.left! > 0) {
      const before = count
      await rsvp(page)
      await expect.poll(async () => changed(before, await readCount(page)), { timeout: 10_000 }).toBe(true)
      count = await readCount(page)
    }

    // Full: the form is gone or disabled, or says so; an attempt changes nothing.
    const submit = button(page, RSVP)
    const blocked =
      (await submit.count()) === 0 || !(await submit.isVisible()) || (await submit.isDisabled())
    if (!blocked) {
      await rsvp(page).catch(() => {})
      await expect(page.getByText(FULL).first()).toBeVisible({ timeout: 10_000 })
    }
    expect((await readCount(page)).left ?? 0).toBe(0)
  })
})

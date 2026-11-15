import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { newVisitor, signUpIfAsked } from '../../helpers/auth'
import { fillIfPresent, unique, uniqueEmail } from '../../helpers/storage'

// Pass check: classes show their spots left; booking one takes a spot, for
// everyone; a full class takes no more bookings.
//
// The prompt does not ask for logins, so the app is only signed up to when
// it asks. Filling a class up is only tried when at most 30 spots are left.

const app = getApp(19)
const url = getAppUrl(app.id)

const BOOK = /book|reserve|join|sign me up|take (a|this) (spot|class)/i
const CONFIRM = /confirm|book|reserve|done|submit/i
const FULL = /full|no (more )?(spots|places|seats)|sold out|waitlist|fully booked/i
const MAX_FILL = 30

// The first class card that has a book button.
function classCard(page: Page): Locator {
  return page
    .locator('li, article, tr, [role="listitem"], [role="row"], section, div')
    .filter({ has: page.getByRole('button', { name: BOOK }) })
    .last()
}

async function className(card: Locator): Promise<string> {
  const heading = card.getByRole('heading').first()
  if ((await heading.count()) > 0) return ((await heading.textContent()) ?? '').trim()
  return ((await card.innerText()).split('\n').find((line) => line.trim().length > 2) ?? '').trim()
}

function cardNamed(page: Page, name: string): Locator {
  return page
    .locator('li, article, tr, [role="listitem"], [role="row"], section, div')
    .filter({ hasText: name })
    .filter({ has: page.getByRole('button') })
    .last()
}

// Spots left for one class, read from text like "8 spots left", "12/15" or
// "Spots: 8".
async function spotsLeft(card: Locator): Promise<number | undefined> {
  const text = (await card.innerText()).replace(/,/g, '')
  const left = text.match(/(\d+)\s*(?:spots?|places?|seats?)?\s*(?:left|remaining|available|open)/i)
  if (left) return Number(left[1])
  const ofLimit = text.match(/(\d+)\s*(?:\/|of|out of)\s*(\d+)/i)
  if (ofLimit) return Number(ofLimit[2]) - Number(ofLimit[1])
  const label = text.match(/(?:spots?|places?|seats?)\s*(?:left)?\s*:\s*(\d+)/i)
  return label ? Number(label[1]) : undefined
}

async function book(page: Page, card: Locator) {
  await card.getByRole('button', { name: BOOK }).first().click()
  // A booking form may ask for details before confirming.
  await fillIfPresent(page, /^(full )?name|your name/i, unique('Yogi'))
  await fillIfPresent(page, /e-?mail/i, uniqueEmail())
  await fillIfPresent(page, /phone|mobile/i, '9876543210')
  const confirm = page.getByRole('button', { name: CONFIRM }).filter({ hasNotText: /cancel/i })
  const dialog = page.getByRole('dialog')
  if ((await dialog.count()) > 0 && (await dialog.isVisible())) {
    await dialog.getByRole('button', { name: CONFIRM }).first().click()
  } else if ((await confirm.count()) > 1) {
    await confirm.last().click()
  }
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
    await signUpIfAsked(page)
  })

  test('classes show how many spots are left', async ({ page }) => {
    const card = classCard(page)
    await expect(card).toBeVisible({ timeout: 10_000 })
    expect(await spotsLeft(card), 'spots left are shown on the class').toBeDefined()
  })

  test('booking a class takes one spot, also for another visitor', async ({ page, browser }) => {
    const card = classCard(page)
    await expect(card).toBeVisible({ timeout: 10_000 })
    const name = await className(card)
    const before = await spotsLeft(cardNamed(page, name))
    test.skip(before === undefined, 'Spots left cannot be read from the page')
    test.skip(before === 0, 'The first class is already full')

    await book(page, cardNamed(page, name))
    await expect.poll(() => spotsLeft(cardNamed(page, name)), { timeout: 10_000 }).toBe(before! - 1)

    const other = await newVisitor(browser, url!)
    try {
      await signUpIfAsked(other.page)
      await expect.poll(() => spotsLeft(cardNamed(other.page, name)), { timeout: 10_000 }).toBe(before! - 1)
    } finally {
      await other.context.close()
    }
  })

  test('a full class takes no more bookings', async ({ page }) => {
    test.setTimeout(240_000)
    const card = classCard(page)
    await expect(card).toBeVisible({ timeout: 10_000 })
    const name = await className(card)
    let left = await spotsLeft(cardNamed(page, name))
    test.skip(left === undefined, 'Spots left cannot be read from the page')
    test.skip(left! > MAX_FILL, `More than ${MAX_FILL} spots left; not filled to the end`)

    while (left! > 0) {
      const before = left!
      await book(page, cardNamed(page, name))
      await expect.poll(() => spotsLeft(cardNamed(page, name)), { timeout: 10_000 }).toBe(before - 1)
      left = before - 1
      // One user may book a class once; the next booking comes from a new visitor.
      await page.context().clearCookies()
      await page.evaluate(() => localStorage.clear())
      await page.reload()
      await signUpIfAsked(page)
    }

    const full = cardNamed(page, name)
    const bookButton = full.getByRole('button', { name: BOOK }).first()
    const blocked = (await bookButton.count()) === 0 || (await bookButton.isDisabled())
    if (!blocked) {
      await book(page, full)
      await expect(page.getByText(FULL).first()).toBeVisible({ timeout: 10_000 })
    }
    expect(await spotsLeft(cardNamed(page, name))).toBe(0)
  })
})

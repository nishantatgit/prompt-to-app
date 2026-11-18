import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { signUpIfAsked } from '../../helpers/auth'
import { asAnotherVisitor, button, field, shown, unique } from '../../helpers/storage'

// Pass check: a seller lists an item with a title, price and photo; the
// photo really loads, and another visitor sees the listing with its photo.

const app = getApp(23)
const url = getAppUrl(app.id)

// A 2x2 red PNG.
const PHOTO = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==',
  'base64',
)

async function listItem(page: Page, title: string) {
  await signUpIfAsked(page)
  const open = page.getByRole('button', { name: /sell|list (an )?item|new listing|add (an )?item|post/i }).first()
  if ((await field(page, /title|name|item/i).count()) === 0 && (await open.count()) > 0) await open.click()
  await field(page, /title|name|item/i).fill(title)
  await field(page, /price|₹|\$|amount/i).fill('499')
  const description = page.getByRole('textbox', { name: /description|details/i }).first()
  if ((await description.count()) > 0) await description.fill('Barely used, collect from Yelahanka.')
  await page.locator('input[type="file"]').first().setInputFiles({ name: 'photo.png', mimeType: 'image/png', buffer: PHOTO })
  await button(page, /list|publish|post|save|create|add|sell/i).click()
  await expect(shown(page, title)).toBeVisible({ timeout: 15_000 })
}

// The photo in the listing has loaded, not just an empty or broken image.
async function photoLoaded(page: Page, title: string) {
  const card = page.locator('article, li, [role="listitem"], div').filter({ has: shown(page, title) }).filter({ has: page.locator('img') }).last()
  const img = card.locator('img').first()
  await expect(img).toBeVisible({ timeout: 15_000 })
  return img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')
  test.setTimeout(60_000)

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('a listing shows its title, price and photo', async ({ page }) => {
    const title = unique('Study table')
    await listItem(page, title)
    await expect(page.getByText(/499/).first()).toBeVisible()
    await expect.poll(() => photoLoaded(page, title), { timeout: 15_000 }).toBe(true)
  })

  test('another visitor sees the listing and its photo', async ({ page, browser }) => {
    const title = unique('Cricket bat')
    await listItem(page, title)
    await asAnotherVisitor(browser, url!, async (visitor) => {
      await expect(shown(visitor, title)).toBeVisible({ timeout: 15_000 })
      await expect.poll(() => photoLoaded(visitor, title), { timeout: 15_000 }).toBe(true)
    })
  })
})

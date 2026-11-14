import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { asAnotherVisitor, button, field, fillIfPresent, itemText, shown, unique } from '../../helpers/storage'

// Pass check: add items with a quantity; an item with very little stock shows
// a low stock warning and one with plenty does not; items are saved on a
// server.
//
// Quantity 1 is low and 500 is plenty under any sensible threshold. When the
// app asks for a threshold per item, it is set to 5.

const app = getApp(14)
const url = getAppUrl(app.id)

const ITEM = /item|product|name/i
const QUANTITY = /quantity|qty|stock|count|units|on hand/i
const THRESHOLD = /threshold|minimum|min\b|reorder|alert|low stock (level|at)/i
const ADD = /add|save|create|new/i
const LOW = /low|reorder|restock|running out/i

async function addItem(page: Page, name: string, quantity: number) {
  await field(page, ITEM).fill(name)
  await field(page, QUANTITY).fill(String(quantity))
  await fillIfPresent(page, THRESHOLD, '5')
  await button(page, ADD).click()
  await expect(shown(page, name)).toBeVisible({ timeout: 10_000 })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('adds an item with its quantity', async ({ page }) => {
    const name = unique('Basmati rice')
    await addItem(page, name, 42)
    expect(await itemText(page, name)).toMatch(/\b42\b/)
  })

  test('an item with little stock is flagged, one with plenty is not', async ({ page }) => {
    const low = unique('Turmeric')
    const plenty = unique('Salt')
    await addItem(page, low, 1)
    await addItem(page, plenty, 500)

    await expect.poll(async () => LOW.test(await itemText(page, low, [plenty])), { timeout: 10_000 }).toBe(true)
    expect(await itemText(page, plenty, [low])).not.toMatch(LOW)
  })

  test('items survive a reload and show in another browser', async ({ page, browser }) => {
    const name = unique('Mustard oil')
    await addItem(page, name, 7)

    await page.reload()
    await expect(shown(page, name)).toBeVisible({ timeout: 10_000 })
    await asAnotherVisitor(browser, url!, async (visitor) => {
      await expect(shown(visitor, name)).toBeVisible({ timeout: 10_000 })
    })
  })
})

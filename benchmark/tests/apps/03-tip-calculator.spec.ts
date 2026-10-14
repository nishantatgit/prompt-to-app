import { test, expect } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: per person amount is mathematically correct.
//
// Locators use labels and loose regex (/bill/i) instead of CSS classes or ids,
// so the test works however the agent writes the code, as long as every
// input has a visible label (part of the app contract).

const app = getApp(3)
const url = getAppUrl(app.id)

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('splits bill plus tip evenly', async ({ page }) => {
    // 1000 + 10% tip = 1100, split by 4 = 275
    await page.getByLabel(/bill/i).fill('1000')
    await page.getByLabel(/tip/i).fill('10')
    await page.getByLabel(/people|persons|split/i).fill('4')

    await expect(page.getByText(/275(\.00)?\b/)).toBeVisible()
  })

  test('handles decimals', async ({ page }) => {
    // 100 + 15% = 115, split by 3 = 38.33
    await page.getByLabel(/bill/i).fill('100')
    await page.getByLabel(/tip/i).fill('15')
    await page.getByLabel(/people|persons|split/i).fill('3')

    await expect(page.getByText(/38\.33/)).toBeVisible()
  })

  test('does not show Infinity or NaN for zero people', async ({ page }) => {
    await page.getByLabel(/bill/i).fill('100')
    await page.getByLabel(/tip/i).fill('10')
    await page.getByLabel(/people|persons|split/i).fill('0')

    await expect(page.getByText(/infinity|nan/i)).toHaveCount(0)
  })
})

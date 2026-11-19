import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: several recipes are listed, and the vegetarian filter leaves
// only recipes without meat or fish, at least one of them.

const app = getApp(10)
const url = getAppUrl(app.id)

const MEAT = /\b(chicken|beef|pork|mutton|lamb|goat|fish|prawns?|shrimps?|crab|bacon|ham|sausages?|turkey|salmon|tuna|keema|anchov(y|ies))\b/i

// The recipe cards or rows on the page: each a heading, list item or article.
async function recipeTitles(page: Page): Promise<string[]> {
  const cards = page.locator('article, li, [role="listitem"]')
  const texts = (await cards.count()) > 0
    ? await cards.allInnerTexts()
    : await page.getByRole('heading', { level: 3 }).allInnerTexts()
  return texts.map((t) => t.trim()).filter(Boolean)
}

async function turnOnVegetarian(page: Page) {
  const name = /veg(etarian|gie)?\b/i
  const toggle = page
    .getByRole('checkbox', { name })
    .or(page.getByRole('switch', { name }))
    .first()
  if ((await toggle.count()) > 0) return toggle.check()
  const chip = page.getByRole('button', { name }).or(page.getByRole('tab', { name })).or(page.getByRole('radio', { name })).first()
  if ((await chip.count()) > 0) return chip.click()
  const select = page.getByRole('combobox').first()
  const label = (await select.locator('option').allTextContents()).find((o) => name.test(o) && !/non/i.test(o))
  await select.selectOption({ label: label! })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('lists several recipes, some with meat or fish', async ({ page }) => {
    const titles = await recipeTitles(page)
    expect(titles.length, 'at least 4 recipes').toBeGreaterThanOrEqual(4)
    expect(titles.some((t) => MEAT.test(t)), 'some recipes are not vegetarian, so the filter matters').toBe(true)
  })

  test('the vegetarian filter hides meat and fish', async ({ page }) => {
    await turnOnVegetarian(page)
    await expect
      .poll(async () => (await recipeTitles(page)).filter((t) => MEAT.test(t)), { message: 'no meat or fish left' })
      .toEqual([])
    expect((await recipeTitles(page)).length, 'some vegetarian recipes remain').toBeGreaterThan(0)
  })
})

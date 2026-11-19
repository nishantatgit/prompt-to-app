import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { button, field, shown, unique } from '../../helpers/storage'

// Pass check: add expenses with a category and amount; the running total is
// the sum, and each expense shows its category.

const app = getApp(7)
const url = getAppUrl(app.id)

const ADD = /add|save|create|record/i

// Choose a category from a select, or type it into a text field.
async function setCategory(page: Page, category: string) {
  const select = page.getByRole('combobox', { name: /category/i }).first()
  if ((await select.count()) > 0) {
    const options = (await select.locator('option').allTextContents()).map((o) => o.trim())
    const match = options.find((o) => o.toLowerCase().includes(category.toLowerCase())) ??
      options.find((o) => o && !/select|choose|--/i.test(o))
    await select.selectOption({ label: match! })
    return match!
  }
  await field(page, /category/i).fill(category)
  return category
}

async function addExpense(page: Page, description: string, amount: string, category: string) {
  const name = field(page, /description|name|title|what|item|note/i)
  if ((await name.count()) > 0) await name.fill(description)
  await field(page, /amount|cost|price|₹|\$/i).fill(amount)
  const chosen = await setCategory(page, category)
  await button(page, ADD).click()
  return chosen
}

// The running total: a number next to the word total.
async function total(page: Page): Promise<number | null> {
  const text = (await page.locator('body').innerText()).replace(/,/g, '')
  const match = text.match(/total[^0-9\n]{0,30}(\d+(?:\.\d+)?)/i)
  return match ? Number(match[1]) : null
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('an expense shows with its category', async ({ page }) => {
    const description = unique('Lunch')
    const category = await addExpense(page, description, '250', 'Food')
    const row = page.locator('li, tr, article, [role="listitem"], [role="row"], div').filter({ hasText: '250' }).filter({ hasText: category }).last()
    await expect(row).toBeVisible()
  })

  test('the total is the sum of the expenses', async ({ page }) => {
    await addExpense(page, unique('Bus'), '120.50', 'Transport')
    await addExpense(page, unique('Groceries'), '79.50', 'Food')
    await expect.poll(() => total(page), { message: 'the total shows 200' }).toBe(200)
  })
})

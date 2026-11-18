import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { button, field, shown, unique } from '../../helpers/storage'

// Pass check: three columns, To Do, Doing and Done; a new card lands in To
// Do and can be moved to Doing and then Done, by a button or by dragging.

const app = getApp(9)
const url = getAppUrl(app.id)

const COLUMNS = { todo: /^\s*to ?do\b/i, doing: /^\s*(doing|in progress)\b/i, done: /^\s*done\b/i }

// The column whose heading matches: the smallest element holding that
// heading and no other column heading.
function column(page: Page, name: RegExp): Locator {
  const heading = page.getByRole('heading', { name }).first()
  return page
    .locator('section, div, ul, [role="list"], [role="region"]')
    .filter({ has: heading })
    .filter({ hasNot: page.getByRole('heading', { name: Object.values(COLUMNS).find((c) => c !== name)! }) })
    .last()
}

async function addCard(page: Page, text: string) {
  await field(page, /task|card|title|what|add/i).fill(text)
  await button(page, /^\+$|add|create|save/i).click()
  await expect(shown(page, text)).toBeVisible()
}

// Move a card one column right: a button on the card, or drag and drop.
async function moveTo(page: Page, text: string, target: keyof typeof COLUMNS) {
  const card = page
    .locator('li, article, [role="listitem"], div')
    .filter({ has: shown(page, text) })
    .filter({ has: page.getByRole('button') })
    .last()
  const targetName = target === 'doing' ? /doing|progress|start|→|›|>|right|next|move/i : /done|complete|finish|→|›|>|right|next|move/i
  const move = card.getByRole('button', { name: targetName })
  const select = card.getByRole('combobox')
  if ((await move.count()) > 0) await move.first().click()
  else if ((await select.count()) > 0) {
    const label = (await select.first().locator('option').allTextContents()).find((o) => COLUMNS[target].test(o))
    await select.first().selectOption({ label: label! })
  } else await shown(page, text).dragTo(column(page, COLUMNS[target]))
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('shows To Do, Doing and Done columns', async ({ page }) => {
    for (const name of Object.values(COLUMNS)) {
      await expect(page.getByRole('heading', { name }).first()).toBeVisible()
    }
  })

  test('a new card starts in To Do', async ({ page }) => {
    const text = unique('Design logo')
    await addCard(page, text)
    await expect(column(page, COLUMNS.todo).getByText(text)).toBeVisible()
  })

  test('a card moves from To Do to Doing to Done', async ({ page }) => {
    const text = unique('Write copy')
    await addCard(page, text)
    await moveTo(page, text, 'doing')
    await expect(column(page, COLUMNS.doing).getByText(text)).toBeVisible()
    await expect(column(page, COLUMNS.todo).getByText(text)).toHaveCount(0)
    await moveTo(page, text, 'done')
    await expect(column(page, COLUMNS.done).getByText(text)).toBeVisible()
    await expect(column(page, COLUMNS.doing).getByText(text)).toHaveCount(0)
  })
})

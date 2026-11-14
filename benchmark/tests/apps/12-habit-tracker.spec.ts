import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { asAnotherVisitor, button, field, itemLocator, itemText, shown, unique } from '../../helpers/storage'

// Pass check: add a habit, check it off for today, and see a streak; the
// habit and its check-off are saved on a server, so a reload and a second
// browser both see them.

const app = getApp(12)
const url = getAppUrl(app.id)

const HABIT = /habit|name|what/i
const ADD = /add|create|save|new|start/i
const CHECK = /check|done|complete|mark|today|✓|✔/i

async function addHabit(page: Page, name: string) {
  await field(page, HABIT).fill(name)
  await button(page, ADD).click()
  await expect(shown(page, name)).toBeVisible({ timeout: 10_000 })
}

// Check the habit off for today, by checkbox or button inside its row.
async function checkOff(page: Page, name: string) {
  const row = itemLocator(page, name)
  const box = row.getByRole('checkbox').first()
  if ((await box.count()) > 0) await box.check()
  else await button(row, CHECK).click()
}

async function isCheckedOff(page: Page, name: string): Promise<boolean> {
  const row = itemLocator(page, name)
  const box = row.getByRole('checkbox').first()
  if ((await box.count()) > 0) return box.isChecked()
  const toggle = row.getByRole('button', { name: CHECK }).first()
  if ((await toggle.count()) > 0) {
    const pressed = await toggle.getAttribute('aria-pressed')
    if (pressed !== null) return pressed === 'true'
  }
  return /done|completed|checked|✓|✔/i.test(await itemText(page, name))
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('adds a habit', async ({ page }) => {
    await addHabit(page, unique('Read 10 pages'))
  })

  test('checking off today shows a streak of 1', async ({ page }) => {
    const name = unique('Drink water')
    await addHabit(page, name)
    await checkOff(page, name)

    await expect.poll(() => isCheckedOff(page, name), { timeout: 10_000 }).toBe(true)
    await expect
      .poll(async () => /(\b1\b\s*(day|streak|🔥))|((streak|🔥)\D{0,12}\b1\b)/i.test(await itemText(page, name)), {
        message: 'the habit shows a streak of 1',
        timeout: 10_000,
      })
      .toBe(true)
  })

  test('the habit and its check-off survive a reload', async ({ page }) => {
    const name = unique('Stretch')
    await addHabit(page, name)
    await checkOff(page, name)
    await expect.poll(() => isCheckedOff(page, name), { timeout: 10_000 }).toBe(true)

    await page.reload()
    await expect(shown(page, name)).toBeVisible({ timeout: 10_000 })
    await expect.poll(() => isCheckedOff(page, name), { timeout: 10_000 }).toBe(true)
  })

  test('another browser sees the habit', async ({ page, browser }) => {
    const name = unique('Walk 5000 steps')
    await addHabit(page, name)
    await asAnotherVisitor(browser, url!, async (visitor) => {
      await expect(shown(visitor, name)).toBeVisible({ timeout: 10_000 })
    })
  })
})

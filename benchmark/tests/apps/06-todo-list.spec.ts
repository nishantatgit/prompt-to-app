import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { button, field, itemLocator, shown, unique } from '../../helpers/storage'

// Pass check: add tasks, complete one, delete one, and filter between all,
// active and completed tasks.

const app = getApp(6)
const url = getAppUrl(app.id)

const TASK = /task|to-?do|what|add/i
const ADD = /^\+$|add|create|save/i
const DELETE = /delete|remove|trash|✕|×|🗑/i

async function addTask(page: Page, text: string) {
  await field(page, TASK).fill(text)
  await button(page, ADD).click()
  await expect(shown(page, text)).toBeVisible()
}

// Complete a task by its checkbox, or a button inside its row.
async function complete(page: Page, text: string) {
  const row = itemLocator(page, text)
  const box = row.getByRole('checkbox').first()
  if ((await box.count()) > 0) await box.check()
  else await button(row, /complete|done|finish|check|✓|✔/i).click()
}

// The filter control for `name`: a button, tab, radio or select option.
async function filter(page: Page, name: RegExp) {
  const control = page
    .getByRole('button', { name })
    .or(page.getByRole('tab', { name }))
    .or(page.getByRole('radio', { name }))
    .first()
  if ((await control.count()) > 0) return control.click()
  await page.getByRole('combobox').first().selectOption({ label: (await page.getByRole('option', { name }).first().textContent())!.trim() })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('adds a task', async ({ page }) => {
    await addTask(page, unique('Buy milk'))
  })

  test('deletes a task', async ({ page }) => {
    const text = unique('Call the plumber')
    await addTask(page, text)
    await button(itemLocator(page, text), DELETE).click()
    await expect(shown(page, text)).toHaveCount(0)
  })

  test('filters active and completed tasks', async ({ page }) => {
    const done = unique('Pay rent')
    const open = unique('Water plants')
    await addTask(page, done)
    await addTask(page, open)
    await complete(page, done)

    await filter(page, /^\s*(completed?|done)\b/i)
    await expect(shown(page, done)).toBeVisible()
    await expect(shown(page, open)).toHaveCount(0)

    await filter(page, /^\s*(active|pending|open|to ?do|remaining)\b/i)
    await expect(shown(page, open)).toBeVisible()
    await expect(shown(page, done)).toHaveCount(0)

    await filter(page, /^\s*all\b/i)
    await expect(shown(page, done)).toBeVisible()
    await expect(shown(page, open)).toBeVisible()
  })
})

import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: a visitor leaves a name and a message, and everyone sees it,
// including after a reload and from a different browser.
//
// The different browser is the check that matters most: it has its own
// storage, so it only sees the entry when the app saved it on a server, not
// in the first visitor's browser.
//
// Saved entries are looked for anywhere on the page except form fields: text
// still typed into a textarea would otherwise match before anything is saved.

const app = getApp(11)
const url = getAppUrl(app.id)

const NAME = /name/i
const MESSAGE = /message|comment|note|wish|entry/i
const SUBMIT = /sign|submit|post|add|leave|send|save/i

function field(page: Page, name: RegExp): Locator {
  return page.getByRole('textbox', { name }).first()
}

function submitButton(page: Page): Locator {
  return page.getByRole('button', { name: SUBMIT }).first()
}

// Shown text, never the value of an input or textarea.
function shown(page: Page, text: string): Locator {
  return page.getByText(text).and(page.locator(':not(textarea):not(input)')).first()
}

function unique(label: string): string {
  return `${label} ${Date.now()}-${Math.floor(Math.random() * 1e6)}`
}

async function sign(page: Page, name: string, message: string) {
  await field(page, NAME).fill(name)
  await field(page, MESSAGE).fill(message)
  await submitButton(page).click()
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('has a name field, a message field and a button to sign', async ({ page }) => {
    await expect(field(page, NAME)).toBeVisible()
    await expect(field(page, MESSAGE)).toBeVisible()
    await expect(submitButton(page)).toBeVisible()
  })

  test('a signed entry shows with its name and message', async ({ page }) => {
    const name = unique('Asha')
    const message = unique('Lovely place, thank you')
    await sign(page, name, message)

    await expect(shown(page, message)).toBeVisible({ timeout: 10_000 })
    await expect(shown(page, name)).toBeVisible()
  })

  test('the entry is still there after a reload', async ({ page }) => {
    const message = unique('Back again next year')
    await sign(page, unique('Ravi'), message)
    await expect(shown(page, message)).toBeVisible({ timeout: 10_000 })

    await page.reload()
    await expect(shown(page, message)).toBeVisible({ timeout: 10_000 })
  })

  test('another visitor sees the entry', async ({ page, browser }) => {
    const message = unique('Hello to the next visitor')
    await sign(page, unique('Meera'), message)
    await expect(shown(page, message)).toBeVisible({ timeout: 10_000 })

    const other = await browser.newContext()
    try {
      const visitor = await other.newPage()
      await visitor.goto(url!)
      await expect(shown(visitor, message)).toBeVisible({ timeout: 10_000 })
    } finally {
      await other.close()
    }
  })

  test('an entry without a message is not saved', async ({ page, browser }) => {
    const name = unique('Nobody')
    await field(page, NAME).fill(name)
    await submitButton(page).click()

    // Give a save time to happen, then look from a fresh browser.
    await page.waitForTimeout(2_000)
    const other = await browser.newContext()
    try {
      const visitor = await other.newPage()
      await visitor.goto(url!)
      await expect(field(visitor, NAME)).toBeVisible()
      await expect(shown(visitor, name)).toHaveCount(0)
    } finally {
      await other.close()
    }
  })
})

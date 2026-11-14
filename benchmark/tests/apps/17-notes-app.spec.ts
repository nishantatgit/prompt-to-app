import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { LOG_OUT, logIn, newVisitor, signUp, testEmail } from '../../helpers/auth'
import { button, field, shown, unique } from '../../helpers/storage'

// Pass check: people sign up and log in with an email and password, write
// notes, and only ever see their own. Signing up must log the user in at
// once: Vyskar turns off email confirmation for apps with logins.

const app = getApp(17)
const url = getAppUrl(app.id)

const NOTE = /note|write|text|content|body|title/i
const ADD = /add|save|create|new note|post/i

async function addNote(page: Page, text: string) {
  await field(page, NOTE).fill(text)
  await button(page, ADD).click()
  await expect(shown(page, text)).toBeVisible({ timeout: 10_000 })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('a new user signs up and is logged in', async ({ page }) => {
    await signUp(page, testEmail('a'))
    await expect(page.getByText(/check your (e-?mail|inbox)|confirm your e-?mail/i)).toHaveCount(0)
  })

  test('a note is saved and survives a reload', async ({ page }) => {
    const note = unique('Buy oat milk')
    await signUp(page, testEmail('b'))
    await addNote(page, note)

    await page.reload()
    await expect(shown(page, note)).toBeVisible({ timeout: 10_000 })
  })

  test('logging out and back in shows the same notes', async ({ page }) => {
    const email = testEmail('c')
    const note = unique('Call the plumber')
    await signUp(page, email)
    await addNote(page, note)

    await button(page, LOG_OUT).click()
    await expect(shown(page, note)).toHaveCount(0)
    await logIn(page, email)
    await expect(shown(page, note)).toBeVisible({ timeout: 10_000 })
  })

  test('another user never sees your notes', async ({ page, browser }) => {
    const note = unique('My private plan')
    await signUp(page, testEmail('d'))
    await addNote(page, note)

    const other = await newVisitor(browser, url!)
    try {
      await signUp(other.page, testEmail('e'))
      await other.page.waitForLoadState('networkidle')
      await expect(shown(other.page, note)).toHaveCount(0)
    } finally {
      await other.context.close()
    }
  })

  test('a logged out visitor sees no notes', async ({ page, browser }) => {
    const note = unique('Bank details reminder')
    await signUp(page, testEmail('f'))
    await addNote(page, note)

    const visitor = await newVisitor(browser, url!)
    try {
      await visitor.page.waitForLoadState('networkidle')
      await expect(shown(visitor.page, note)).toHaveCount(0)
    } finally {
      await visitor.context.close()
    }
  })
})

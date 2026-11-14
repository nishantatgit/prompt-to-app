import { test, expect, type Browser, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { button, field, shown, unique } from '../../helpers/storage'

// Pass check: people sign up and log in with an email and password, write
// notes, and only ever see their own. Signing up must log the user in at
// once: Vyskar turns off email confirmation for apps with logins.
//
// Each test signs up fresh users with unique emails, on a real email domain
// so the address passes Supabase's checks; no email is ever sent.

const app = getApp(17)
const url = getAppUrl(app.id)

const PASSWORD = 'Test-password-123'
const SIGN_UP = /sign ?up|register|create (an |my )?account/i
const LOG_IN = /log ?in|sign ?in/i
const LOG_OUT = /log ?out|sign ?out/i
const NOTE = /note|write|text|content|body|title/i
const ADD = /add|save|create|new note|post/i

function email(tag: string) {
  return `vyskar.bench+${Date.now()}${Math.floor(Math.random() * 1e4)}${tag}@gmail.com`
}

// Open the form for `action`, switching to it when the page shows the other.
async function openForm(page: Page, action: RegExp) {
  const submit = page.getByRole('button', { name: action }).first()
  if ((await submit.count()) > 0 && (await submit.isVisible())) return
  const toggle = page
    .getByRole('link', { name: action })
    .or(page.getByRole('button', { name: action }))
    .or(page.getByRole('tab', { name: action }))
    .or(page.getByText(action))
    .first()
  await toggle.click()
  await expect(page.getByRole('button', { name: action }).first()).toBeVisible()
}

async function signUp(page: Page, address: string) {
  await openForm(page, SIGN_UP)
  await field(page, /e-?mail/i).fill(address)
  await page.getByLabel(/password/i).first().fill(PASSWORD)
  const confirm = page.getByLabel(/confirm|repeat|again/i)
  if ((await confirm.count()) > 0) await confirm.first().fill(PASSWORD)
  await button(page, SIGN_UP).click()
  await expect(button(page, LOG_OUT), 'signing up logs the user in at once').toBeVisible({
    timeout: 15_000,
  })
}

async function logIn(page: Page, address: string) {
  await openForm(page, LOG_IN)
  await field(page, /e-?mail/i).fill(address)
  await page.getByLabel(/password/i).first().fill(PASSWORD)
  await button(page, LOG_IN).click()
  await expect(button(page, LOG_OUT)).toBeVisible({ timeout: 15_000 })
}

async function addNote(page: Page, text: string) {
  await field(page, NOTE).fill(text)
  await button(page, ADD).click()
  await expect(shown(page, text)).toBeVisible({ timeout: 10_000 })
}

async function freshVisitor(browser: Browser) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(url!)
  return { context, page }
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('a new user signs up and is logged in', async ({ page }) => {
    await signUp(page, email('a'))
    await expect(page.getByText(/check your (e-?mail|inbox)|confirm your e-?mail/i)).toHaveCount(0)
  })

  test('a note is saved and survives a reload', async ({ page }) => {
    const note = unique('Buy oat milk')
    await signUp(page, email('b'))
    await addNote(page, note)

    await page.reload()
    await expect(shown(page, note)).toBeVisible({ timeout: 10_000 })
  })

  test('logging out and back in shows the same notes', async ({ page }) => {
    const address = email('c')
    const note = unique('Call the plumber')
    await signUp(page, address)
    await addNote(page, note)

    await button(page, LOG_OUT).click()
    await expect(shown(page, note)).toHaveCount(0)
    await logIn(page, address)
    await expect(shown(page, note)).toBeVisible({ timeout: 10_000 })
  })

  test('another user never sees your notes', async ({ page, browser }) => {
    const note = unique('My private plan')
    await signUp(page, email('d'))
    await addNote(page, note)

    const other = await freshVisitor(browser)
    try {
      await signUp(other.page, email('e'))
      await other.page.waitForLoadState('networkidle')
      await expect(shown(other.page, note)).toHaveCount(0)
    } finally {
      await other.context.close()
    }
  })

  test('a logged out visitor sees no notes', async ({ page, browser }) => {
    const note = unique('Bank details reminder')
    await signUp(page, email('f'))
    await addNote(page, note)

    const visitor = await freshVisitor(browser)
    try {
      await visitor.page.waitForLoadState('networkidle')
      await expect(shown(visitor.page, note)).toHaveCount(0)
    } finally {
      await visitor.context.close()
    }
  })
})

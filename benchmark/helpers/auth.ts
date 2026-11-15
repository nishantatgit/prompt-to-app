import { expect, type Browser, type Page } from '@playwright/test'
import { button, field } from './storage'

// Sign up and log in for apps with logins (level 4). Vyskar turns off email
// confirmation, so signing up logs the user in at once. Each test signs up
// fresh users on a real email domain so the address passes Supabase's
// checks; no email is ever sent.

export const PASSWORD = 'Test-password-123'
export const SIGN_UP = /sign ?up|register|create (an |my )?account/i
export const LOG_IN = /log ?in|sign ?in/i
export const LOG_OUT = /log ?out|sign ?out/i

export function testEmail(tag = ''): string {
  return `vyskar.bench+${Date.now()}${Math.floor(Math.random() * 1e4)}${tag}@gmail.com`
}

// Show the form for `action`, switching to it when the page shows the other.
async function openForm(page: Page, action: RegExp) {
  const submit = page.getByRole('button', { name: action }).first()
  if ((await submit.count()) > 0 && (await submit.isVisible())) return
  await page
    .getByRole('link', { name: action })
    .or(page.getByRole('button', { name: action }))
    .or(page.getByRole('tab', { name: action }))
    .or(page.getByText(action))
    .first()
    .click()
  await expect(page.getByRole('button', { name: action }).first()).toBeVisible()
}

async function fillCredentials(page: Page, email: string) {
  await field(page, /e-?mail/i).fill(email)
  await page.getByLabel(/password/i).first().fill(PASSWORD)
  const confirm = page.getByLabel(/confirm|repeat|again/i)
  if ((await confirm.count()) > 0) await confirm.first().fill(PASSWORD)
  const name = page.getByRole('textbox', { name: /^(full )?name|display name|your name/i })
  if ((await name.count()) > 0 && (await name.first().isVisible())) await name.first().fill('Bench User')
}

export async function signUp(page: Page, email = testEmail()): Promise<string> {
  await openForm(page, SIGN_UP)
  await fillCredentials(page, email)
  await button(page, SIGN_UP).click()
  await expect(button(page, LOG_OUT), 'signing up logs the user in at once').toBeVisible({
    timeout: 15_000,
  })
  return email
}

export async function logIn(page: Page, email: string) {
  await openForm(page, LOG_IN)
  await fillCredentials(page, email)
  await button(page, LOG_IN).click()
  await expect(button(page, LOG_OUT)).toBeVisible({ timeout: 15_000 })
}

export async function isLoggedIn(page: Page): Promise<boolean> {
  const out = button(page, LOG_OUT)
  return (await out.count()) > 0 && (await out.isVisible())
}

// For apps where the prompt does not say logins are required: sign up only
// when the page asks for it, such as a password field with no way past it.
export async function signUpIfAsked(page: Page): Promise<string | null> {
  await page.waitForLoadState('networkidle')
  if (await isLoggedIn(page)) return null
  const password = page.getByLabel(/password/i)
  if ((await password.count()) === 0 || !(await password.first().isVisible())) return null
  return signUp(page)
}

export async function newVisitor(browser: Browser, url: string) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(url)
  return { context, page }
}

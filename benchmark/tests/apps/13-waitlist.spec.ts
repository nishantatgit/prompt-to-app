import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { asAnotherVisitor, button, field, shown, uniqueEmail } from '../../helpers/storage'

// Pass check: a visitor joins the waitlist with an email, a bad email is
// refused, and an admin list shows the emails that signed up, saved on a
// server.
//
// The admin list is found by a link or button named "admin", or at /admin.
// The prompt does not ask for a password, so an admin page behind one is
// reported as skipped, not failed.

const app = getApp(13)
const url = getAppUrl(app.id)

const EMAIL = /e-?mail/i
const JOIN = /join|sign ?up|subscribe|notify|waitlist|submit|request|get early/i
const ADMIN = /admin/i
const SUCCESS = /thank|you('| a)re (on|in)|added|joined|success|confirmed|on the (wait)?list|we('|wi)ll/i

async function join(page: Page, email: string) {
  await field(page, EMAIL).fill(email)
  await button(page, JOIN).click()
}

// Open the admin list; returns false when it is behind a password.
async function openAdmin(page: Page): Promise<boolean> {
  const link = page.getByRole('link', { name: ADMIN }).or(page.getByRole('button', { name: ADMIN })).first()
  if ((await link.count()) > 0 && (await link.isVisible())) await link.click()
  else await page.goto(new URL('/admin', url!).toString())
  await page.waitForLoadState('networkidle')
  const password = page.locator('input[type="password"]')
  return (await password.count()) === 0
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('has an email field and a button to join', async ({ page }) => {
    await expect(field(page, EMAIL)).toBeVisible()
    await expect(button(page, JOIN)).toBeVisible()
  })

  test('joining with a valid email confirms it', async ({ page }) => {
    await join(page, uniqueEmail())
    await expect(page.getByText(SUCCESS).first()).toBeVisible({ timeout: 10_000 })
  })

  test('a badly formed email is refused', async ({ page }) => {
    await join(page, 'not-an-email')
    const input = field(page, EMAIL)
    const refused = await input.evaluate((el: HTMLInputElement) => !el.checkValidity())
    if (!refused) {
      await expect(
        page.getByRole('alert').or(page.getByText(/valid e-?mail|invalid|enter an e-?mail/i)).first(),
      ).toBeVisible({ timeout: 5_000 })
    }
    await expect(page.getByText(SUCCESS)).toHaveCount(0)
  })

  test('the admin list shows the new email, also in another browser', async ({ page, browser }) => {
    const email = uniqueEmail()
    await join(page, email)
    await expect(page.getByText(SUCCESS).first()).toBeVisible({ timeout: 10_000 })

    await asAnotherVisitor(browser, url!, async (admin) => {
      const open = await openAdmin(admin)
      test.skip(!open, 'The admin list is behind a password the prompt does not give')
      await expect(shown(admin, email)).toBeVisible({ timeout: 10_000 })
    })
  })
})

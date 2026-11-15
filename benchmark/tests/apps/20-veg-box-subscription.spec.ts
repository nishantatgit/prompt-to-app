import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { newVisitor, signUpIfAsked } from '../../helpers/auth'
import { fillIfPresent, shown, unique, uniqueEmail } from '../../helpers/storage'

// Pass check: a customer subscribes to the weekly box and sees their
// subscription; the admin order view lists orders, but other customers and
// logged out visitors never see someone else's order.
//
// The prompt gives no admin login, so the admin view itself is not opened
// with admin rights. What is checked is that it does not leak: opened at
// /admin, or through a link named admin, it must not show a customer's
// details to anyone else.

const app = getApp(20)
const url = getAppUrl(app.id)

const SUBSCRIBE = /subscribe|start|order|sign me up|get (my|the|a) box|confirm|checkout/i
const SUCCESS = /thank|subscribed|subscription (is )?(active|confirmed)|order (placed|confirmed)|you('|’)re (in|subscribed)|welcome|confirmed/i
const ADMIN = /admin|orders/i

type Customer = { name: string; email: string }

async function subscribe(page: Page): Promise<Customer> {
  const customer = { name: unique('Asha Rao'), email: uniqueEmail() }
  await signUpIfAsked(page)
  // A box size or plan may need choosing first.
  const radio = page.getByRole('radio').first()
  if ((await radio.count()) > 0 && (await radio.isVisible()) && !(await radio.isChecked())) await radio.check()
  const select = page.getByRole('combobox').first()
  if ((await select.count()) > 0 && (await select.isVisible())) {
    const options = await select.locator('option').evaluateAll((els) =>
      els.map((el) => (el as HTMLOptionElement).value).filter(Boolean),
    )
    if (options.length) await select.selectOption(options[0])
  }
  await fillIfPresent(page, /^(full )?name|your name/i, customer.name)
  await fillIfPresent(page, /e-?mail/i, customer.email)
  await fillIfPresent(page, /address|street/i, '12 MG Road, Bengaluru 560001')
  await fillIfPresent(page, /phone|mobile/i, '9876543210')
  await page.getByRole('button', { name: SUBSCRIBE }).first().click()
  await expect(page.getByText(SUCCESS).first()).toBeVisible({ timeout: 15_000 })
  return customer
}

async function openAdmin(page: Page) {
  const link = page.getByRole('link', { name: ADMIN }).or(page.getByRole('button', { name: ADMIN })).first()
  if ((await link.count()) > 0 && (await link.isVisible())) await link.click()
  else await page.goto(new URL('/admin', url!).toString())
  await page.waitForLoadState('networkidle')
}

async function expectNoLeak(page: Page, customer: Customer) {
  await expect(shown(page, customer.email)).toHaveCount(0)
  await expect(shown(page, customer.name)).toHaveCount(0)
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('a customer subscribes to the weekly box', async ({ page }) => {
    await subscribe(page)
  })

  test('the subscription is still there after a reload', async ({ page }) => {
    await subscribe(page)
    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByText(/subscri|your (box|order)|weekly/i).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/cancel|pause|next (box|delivery)|active|manage/i).first()).toBeVisible({
      timeout: 10_000,
    })
  })

  test('a logged out visitor cannot see orders in the admin view', async ({ page, browser }) => {
    const customer = await subscribe(page)
    const visitor = await newVisitor(browser, url!)
    try {
      await openAdmin(visitor.page)
      await expectNoLeak(visitor.page, customer)
    } finally {
      await visitor.context.close()
    }
  })

  test("another customer cannot see someone else's order", async ({ page, browser }) => {
    const customer = await subscribe(page)
    const other = await newVisitor(browser, url!)
    try {
      await signUpIfAsked(other.page)
      await expectNoLeak(other.page, customer)
      await openAdmin(other.page)
      await expectNoLeak(other.page, customer)
    } finally {
      await other.context.close()
    }
  })
})

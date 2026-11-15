import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { newVisitor, signUp, testEmail } from '../../helpers/auth'
import { button, field, itemLocator, shown, unique } from '../../helpers/storage'

// Pass check: logged in users write posts, and anyone can read them. A
// logged out visitor cannot write, and one user cannot edit or delete
// another user's post.

const app = getApp(18)
const url = getAppUrl(app.id)

const OPEN_EDITOR = /new post|write|create( a)? post|compose|add post/i
const TITLE = /title|headline/i
const BODY = /body|content|story|text|write|post/i
const PUBLISH = /publish|post|save|submit|create/i
const EDIT_OR_DELETE = /edit|delete|remove/i

async function openEditor(page: Page) {
  const title = field(page, TITLE)
  if ((await title.count()) > 0 && (await title.isVisible())) return
  await page
    .getByRole('button', { name: OPEN_EDITOR })
    .or(page.getByRole('link', { name: OPEN_EDITOR }))
    .first()
    .click()
  await expect(field(page, TITLE)).toBeVisible()
}

async function writePost(page: Page, title: string) {
  await openEditor(page)
  await field(page, TITLE).fill(title)
  const body = page.getByRole('textbox', { name: BODY }).and(page.locator(':not([type="email"])')).last()
  await body.fill(`Written for the benchmark: ${title}. A few sentences about the morning walk.`)
  await button(page, PUBLISH).click()
  await expect(shown(page, title)).toBeVisible({ timeout: 10_000 })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('a logged in user writes a post that survives a reload', async ({ page }) => {
    const title = unique('Morning walks in Cubbon Park')
    await signUp(page, testEmail('a'))
    await writePost(page, title)

    await page.reload()
    await expect(shown(page, title)).toBeVisible({ timeout: 10_000 })
  })

  test('a logged out visitor can read the post', async ({ page, browser }) => {
    const title = unique('Why I switched to cycling')
    await signUp(page, testEmail('b'))
    await writePost(page, title)

    const visitor = await newVisitor(browser, url!)
    try {
      await expect(shown(visitor.page, title)).toBeVisible({ timeout: 10_000 })
    } finally {
      await visitor.context.close()
    }
  })

  test('a logged out visitor cannot write a post', async ({ page }) => {
    await page.waitForLoadState('networkidle')
    const title = field(page, TITLE)
    if ((await title.count()) > 0 && (await title.isVisible())) {
      // An editor shown to visitors must not publish anything.
      const attempt = unique('Visitor post')
      await title.fill(attempt)
      await button(page, PUBLISH).click()
      await page.waitForTimeout(2_000)
      await page.reload()
      await expect(shown(page, attempt)).toHaveCount(0)
      return
    }
    const open = page.getByRole('button', { name: OPEN_EDITOR }).or(page.getByRole('link', { name: OPEN_EDITOR })).first()
    if ((await open.count()) > 0 && (await open.isVisible())) {
      await open.click()
      // Asking to log in is fine; an editor that opens is not.
      await expect(field(page, TITLE)).toHaveCount(0)
    }
  })

  test("another user cannot edit or delete someone else's post", async ({ page, browser }) => {
    const title = unique('Notes from the farmers market')
    await signUp(page, testEmail('c'))
    await writePost(page, title)

    const other = await newVisitor(browser, url!)
    try {
      await signUp(other.page, testEmail('d'))
      await expect(shown(other.page, title)).toBeVisible({ timeout: 10_000 })
      const post = itemLocator(other.page, title)
      await expect(post.getByRole('button', { name: EDIT_OR_DELETE })).toHaveCount(0)
    } finally {
      await other.context.close()
    }
  })
})

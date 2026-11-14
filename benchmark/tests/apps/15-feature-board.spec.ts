import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import {
  asAnotherVisitor,
  button,
  field,
  itemLocator,
  itemText,
  numbersIn,
  shown,
  unique,
} from '../../helpers/storage'

// Pass check: post a feature request, upvote it, and see its count go up by
// one; requests and votes are saved on a server, so a second browser sees
// the same count.

const app = getApp(15)
const url = getAppUrl(app.id)

const TITLE = /title|feature|idea|request|suggest/i
const POST = /submit|post|add|request|suggest|create|send/i
const UPVOTE = /up ?vote|vote|like|\+1|▲|👍|⬆/i

async function post(page: Page, title: string) {
  await field(page, TITLE).fill(title)
  await button(page, POST).click()
  await expect(shown(page, title)).toBeVisible({ timeout: 10_000 })
}

// The vote count: the number on the upvote button, or the only number left
// in the request's row once numbers from the title are taken out.
async function votes(page: Page, title: string): Promise<number> {
  const upvote = itemLocator(page, title).getByRole('button', { name: UPVOTE }).first()
  const onButton = numbersIn((await upvote.textContent()) ?? '')
  if (onButton.length === 1) return onButton[0]
  const inTitle = new Set(numbersIn(title))
  const rest = numbersIn(await itemText(page, title)).filter((n) => !inTitle.has(n))
  if (rest.length !== 1) throw new Error(`could not find one vote count near "${title}": ${rest}`)
  return rest[0]
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('posts a feature request', async ({ page }) => {
    await post(page, unique('Dark mode for the dashboard'))
  })

  test('an upvote adds one to the count', async ({ page }) => {
    const title = unique('Export to CSV')
    await post(page, title)
    const before = await votes(page, title)

    await itemLocator(page, title).getByRole('button', { name: UPVOTE }).first().click()
    await expect.poll(() => votes(page, title), { timeout: 10_000 }).toBe(before + 1)
  })

  test('another browser sees the request and its votes', async ({ page, browser }) => {
    const title = unique('Weekly email summary')
    await post(page, title)
    await itemLocator(page, title).getByRole('button', { name: UPVOTE }).first().click()
    await expect.poll(() => votes(page, title), { timeout: 10_000 }).toBeGreaterThan(0)
    const count = await votes(page, title)

    await asAnotherVisitor(browser, url!, async (visitor) => {
      await expect(shown(visitor, title)).toBeVisible({ timeout: 10_000 })
      await expect.poll(() => votes(visitor, title), { timeout: 10_000 }).toBe(count)
    })
  })
})

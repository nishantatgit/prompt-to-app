import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: uploading a CSV shows a chart drawn from it, and its data
// (column names or values) on the page; a file that is not a CSV gets an
// error, not a blank or broken page.

const app = getApp(25)
const url = getAppUrl(app.id)

const CSV = 'Month,Sales,Visitors\nJan,120,900\nFeb,180,1100\nMar,150,1050\nApr,240,1500\nMay,210,1320\n'

async function upload(page: Page, name: string, body: string, mimeType = 'text/csv') {
  await page.locator('input[type="file"]').first().setInputFiles({ name, mimeType, buffer: Buffer.from(body) })
}

// A drawn chart: a canvas, or an SVG with several marks, of real size.
async function chartDrawn(page: Page) {
  return page.evaluate(() => {
    const big = (el: Element) => {
      const r = el.getBoundingClientRect()
      return r.width > 100 && r.height > 60
    }
    const canvas = [...document.querySelectorAll('canvas')].some(big)
    const svg = [...document.querySelectorAll('svg')].some(
      (s) => big(s) && s.querySelectorAll('rect, path, circle, line, polyline').length >= 5,
    )
    return canvas || svg
  })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('uploading a CSV draws a chart from its data', async ({ page }) => {
    await upload(page, 'sales.csv', CSV)
    await expect.poll(() => chartDrawn(page), { message: 'a chart is drawn', timeout: 10_000 }).toBe(true)
    const text = await page.locator('body').innerText()
    expect(/sales|visitors/i.test(text) || /\b(240|1500|Jan|May)\b/.test(text), 'the CSV data shows on the page').toBe(true)
  })

  test('a file that is not a CSV gets a clear error', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await upload(page, 'notes.txt', 'this is just some text\nwith no columns', 'text/plain')
    await expect(page.getByText(/error|invalid|couldn.?t|could not|not a (valid )?csv|unable|failed|no (data|columns)/i).first()).toBeVisible({ timeout: 10_000 })
    expect(errors, 'no crash in the page').toEqual([])
  })
})

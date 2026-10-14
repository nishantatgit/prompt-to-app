import { test, expect } from '@playwright/test'
import { apps, getAppUrl, tagsFor } from '../../helpers/apps'

// These checks run against every deployed app, whatever it does.

for (const app of apps) {
  const url = getAppUrl(app.id)

  test.describe(`#${app.id} ${app.slug} | common`, { tag: tagsFor(app) }, () => {
    test.skip(!url, 'Not deployed yet')

    test('page loads', async ({ page }) => {
      const response = await page.goto(url!)
      expect(response?.status()).toBeLessThan(400)
      await expect(page.locator('body')).not.toBeEmpty()
    })

    test('no console errors', async ({ page }) => {
      const errors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') errors.push(msg.text())
      })
      page.on('pageerror', (err) => errors.push(err.message))

      await page.goto(url!)
      await page.waitForLoadState('networkidle')

      expect(errors).toEqual([])
    })

    test('fits a mobile screen', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 812 })
      await page.goto(url!)

      const scrollsSideways = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      )
      expect(scrollsSideways).toBe(false)
    })
  })
}

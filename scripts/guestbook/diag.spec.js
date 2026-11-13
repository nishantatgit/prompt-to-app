import { test } from '@playwright/test'

test('log what the browser sends', async ({ page }) => {
  page.on('console', (m) => console.log(`console ${m.type()}: ${m.text().slice(0, 300)}`))
  page.on('requestfailed', (r) => console.log(`request failed: ${r.method()} ${new URL(r.url()).pathname} ${r.failure()?.errorText}`))
  page.on('response', async (r) => {
    if (!r.url().includes('/rest/v1/')) return
    const body = await r.text().catch(() => '')
    const h = r.request().headers()
    console.log(`${r.request().method()} ${new URL(r.url()).pathname}${new URL(r.url()).search.slice(0, 80)} -> ${r.status()} ${body.slice(0, 300)} | prefer=${h['prefer'] ?? ''} auth=${(h['authorization'] ?? '').slice(0, 12)}`)
  })
  await page.goto('/')
  await page.waitForTimeout(2000)
  await page.getByLabel('Name').fill('Asha')
  await page.getByLabel('Message').fill('diagnostic hello')
  await page.getByRole('button', { name: 'Sign the guestbook' }).click()
  await page.waitForTimeout(4000)
  console.log('alerts:', await page.getByRole('alert').allInnerTexts())
  console.log('list:', await page.getByRole('list', { name: 'Entries' }).innerText())
})

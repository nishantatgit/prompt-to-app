import { test, expect } from '@playwright/test'

test('the real save test, with request logging', async ({ page }) => {
  page.on('console', (m) => console.log(`console ${m.type()}: ${m.text().slice(0, 300)}`))
  page.on('response', async (r) => {
    if (!r.url().includes('/rest/v1/')) return
    const body = await r.text().catch(() => '')
    console.log(`${r.request().method()} -> ${r.status()} ${body.slice(0, 200)} | cache-control=${r.headers()['cache-control'] ?? ''} age=${r.headers()['age'] ?? ''} cf=${r.headers()['cf-cache-status'] ?? ''} fromCache=${r.fromServiceWorker?.() ?? ''}`)
  })
  const message = `Hello from test ${Date.now()}`
  await page.goto('/')
  await page.getByLabel('Name').fill('Asha')
  await page.getByLabel('Message').fill(message)
  await page.getByRole('button', { name: 'Sign the guestbook' }).click()
  await expect(page.getByText(message)).toBeVisible()
  console.log('--- reload')
  await page.reload()
  await page.waitForTimeout(3000)
  console.log('list after reload:', JSON.stringify(await page.getByRole('list', { name: 'Entries' }).innerText()))
})

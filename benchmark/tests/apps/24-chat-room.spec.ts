import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { signUpIfAsked } from '../../helpers/auth'
import { field, shown, unique } from '../../helpers/storage'

// Pass check: two people in the chat room; a message one sends appears for
// the other within seconds, without reloading the page.

const app = getApp(24)
const url = getAppUrl(app.id)

// Join the room: sign up or pick a name when the app asks.
async function join(page: Page, name: string) {
  await signUpIfAsked(page)
  const nickname = page.getByRole('textbox', { name: /^(your )?(nick)?name|display name|username/i }).first()
  if ((await nickname.count()) > 0 && (await nickname.isVisible())) {
    await nickname.fill(name)
    const enter = page.getByRole('button', { name: /join|enter|start|continue|go/i }).first()
    if ((await enter.count()) > 0) await enter.click()
  }
}

async function send(page: Page, text: string) {
  const box = field(page, /message|type|say|write|chat/i)
  await box.fill(text)
  const sendButton = page.getByRole('button', { name: /send|➤|post/i }).first()
  if ((await sendButton.count()) > 0) await sendButton.click()
  else await box.press('Enter')
  await expect(shown(page, text)).toBeVisible({ timeout: 10_000 })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')
  test.setTimeout(60_000)

  test('a message appears live for the other person, both ways', async ({ browser }) => {
    const a = await browser.newContext()
    const b = await browser.newContext()
    try {
      const pa = await a.newPage()
      const pb = await b.newPage()
      await pa.goto(url!)
      await pb.goto(url!)
      await join(pa, 'Asha')
      await join(pb, 'Ravi')

      const hello = unique('Hello from Asha')
      await send(pa, hello)
      await expect(shown(pb, hello), 'appears without a reload').toBeVisible({ timeout: 10_000 })

      const reply = unique('Hi Asha, Ravi here')
      await send(pb, reply)
      await expect(shown(pa, reply), 'appears without a reload').toBeVisible({ timeout: 10_000 })
    } finally {
      await a.close()
      await b.close()
    }
  })

  test('messages are still there after a reload', async ({ page }) => {
    await page.goto(url!)
    await join(page, 'Meera')
    const text = unique('Anyone up for chai?')
    await send(page, text)
    await page.reload()
    await join(page, 'Meera')
    await expect(shown(page, text)).toBeVisible({ timeout: 10_000 })
  })
})


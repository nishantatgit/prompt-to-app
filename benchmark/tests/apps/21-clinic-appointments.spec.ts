import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { newVisitor, signUpIfAsked } from '../../helpers/auth'
import { fillIfPresent, shown, unique, uniqueEmail } from '../../helpers/storage'

// Pass check: patients see doctors and their free slots, book one, and the
// booked slot is no longer offered to anyone else, so a slot is never booked
// twice. Other visitors never see who booked it.
//
// The prompt does not ask for logins, so the app is only signed up to when
// it asks. A slot is a button whose name holds a time, such as "10:30" or
// "3 PM".

const app = getApp(21)
const url = getAppUrl(app.id)

const DOCTOR = /dr\.?\s|doctor/i
const SLOT = /\b\d{1,2}([:.]\d{2})\s*(am|pm)?\b|\b\d{1,2}\s*(am|pm)\b/i
const CONFIRM = /confirm|book|request|submit|done/i
const SUCCESS = /booked|confirmed|appointment (is )?(set|scheduled|booked)|see you|thank/i

function slots(scope: Page | Locator): Locator {
  return scope.getByRole('button', { name: SLOT }).and(scope.locator(':not([disabled])'))
}

// Choose a doctor when the page asks for one before showing slots.
async function chooseDoctor(page: Page) {
  if ((await slots(page).count()) > 0) return
  const select = page.getByRole('combobox').first()
  if ((await select.count()) > 0 && (await select.isVisible())) {
    const values = await select.locator('option').evaluateAll((els) =>
      els.map((el) => (el as HTMLOptionElement).value).filter(Boolean),
    )
    if (values.length) await select.selectOption(values[0])
  } else {
    const doctor = page
      .getByRole('button', { name: DOCTOR })
      .or(page.getByRole('link', { name: DOCTOR }))
      .or(page.getByRole('radio', { name: DOCTOR }))
      .first()
    if ((await doctor.count()) > 0) await doctor.click()
  }
  await expect(slots(page).first()).toBeVisible({ timeout: 10_000 })
}

// The slot's name, such as "10:30 AM".
async function slotLabel(slot: Locator): Promise<string> {
  return ((await slot.getAttribute('aria-label')) ?? (await slot.innerText())).trim()
}

function freeSlotsNamed(page: Page, slot: string): Promise<number> {
  return page
    .getByRole('button', { name: slot, exact: true })
    .and(page.locator(':not([disabled])'))
    .count()
}

// Books the first free slot. `free` is how many free slots had that same
// name before booking, since several doctors or days can share a time.
async function bookFirstSlot(page: Page): Promise<{ slot: string; patient: string; free: number }> {
  await chooseDoctor(page)
  const first = slots(page).first()
  const slot = await slotLabel(first)
  const free = await freeSlotsNamed(page, slot)
  await first.click()
  const patient = unique('Meera Iyer')
  await fillIfPresent(page, /^(full |patient )?name|your name/i, patient)
  await fillIfPresent(page, /e-?mail/i, uniqueEmail())
  await fillIfPresent(page, /phone|mobile/i, '9876543210')
  await fillIfPresent(page, /reason|symptom|note/i, 'Routine check up')
  const confirm = page.getByRole('button', { name: CONFIRM }).filter({ hasNotText: SLOT })
  if ((await confirm.count()) > 0) await confirm.last().click()
  await expect(page.getByText(SUCCESS).first()).toBeVisible({ timeout: 15_000 })
  return { slot, patient, free }
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
    await signUpIfAsked(page)
  })

  test('shows doctors and their free slots', async ({ page }) => {
    await expect(page.getByText(DOCTOR).first()).toBeVisible({ timeout: 10_000 })
    await chooseDoctor(page)
    expect(await slots(page).count()).toBeGreaterThan(0)
  })

  test('a patient books a slot', async ({ page }) => {
    await bookFirstSlot(page)
  })

  test('a booked slot is not offered to anyone else', async ({ page, browser }) => {
    const { slot, free } = await bookFirstSlot(page)

    const other = await newVisitor(browser, url!)
    try {
      await signUpIfAsked(other.page)
      await chooseDoctor(other.page)
      expect(await freeSlotsNamed(other.page, slot), `"${slot}" is still offered after it was booked`).toBe(
        free - 1,
      )
    } finally {
      await other.context.close()
    }
  })

  test('other visitors never see who booked', async ({ page, browser }) => {
    const { patient } = await bookFirstSlot(page)

    const other = await newVisitor(browser, url!)
    try {
      await signUpIfAsked(other.page)
      await other.page.waitForLoadState('networkidle')
      await expect(shown(other.page, patient)).toHaveCount(0)
    } finally {
      await other.context.close()
    }
  })
})

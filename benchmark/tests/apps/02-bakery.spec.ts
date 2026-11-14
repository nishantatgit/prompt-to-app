import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: the landing page names the bakery at the top, opens with a hero
// image, video or gradient placeholder, shows a menu and has a contact form
// that rejects empty fields and a badly formatted email, and confirms a valid
// submission.
//
// Placeholder names and images count. Page loads and mobile fit are covered
// by the common checks.

const app = getApp(2)
const url = getAppUrl(app.id)

// Headings that are page labels, not a bakery's name.
const GENERIC_TITLE = /^(the |our |my )?(bakery|welcome|home|menu|landing page)!?$/i

// The bakery's name may be the main heading or the first text in the page
// header, next to the logo. Both are read from the first screen.
async function bakeryNameCandidates(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const fold = window.innerHeight
    const inFirstScreen = (el: Element | null) =>
      !!el && (el as HTMLElement).checkVisibility() && el.getBoundingClientRect().top < fold
    const found: string[] = []
    const h1 = document.querySelector('h1')
    if (inFirstScreen(h1)) found.push((h1 as HTMLElement).innerText.trim())
    const header = document.querySelector('header, [role="banner"]')
    if (inFirstScreen(header)) {
      const first = (header as HTMLElement).innerText.split('\n').map((l) => l.trim()).find(Boolean)
      if (first) found.push(first)
    }
    return found
  })
}

// A name is short, not a generic word, and not a sentence. A tagline such as
// "Freshly baked, made with care" or "Baked fresh every day." reads as a
// sentence; "Crumb & Co." does not, since the full stop ends an abbreviation.
// Placeholders such as "Your Bakery Name" count.
function looksLikeName(text: string): boolean {
  const words = text.split(/\s+/).filter(Boolean)
  const sentence = /[,!?]|\.\s/.test(text) || (text.endsWith('.') && words.length > 3)
  return (
    words.length >= 1 &&
    words.length <= 6 &&
    text.length <= 40 &&
    !sentence &&
    !GENERIC_TITLE.test(text)
  )
}

// Hero media in the first screen: an image, video or background image of at
// least 80 by 80 px, or a colored gradient of at least 200 by 150 px as a
// placeholder. Small icons, and plain colored shapes with an icon, do not count.
async function heroMediaCount(page: Page): Promise<number> {
  return page.evaluate(() => {
    const fold = window.innerHeight
    const isImage = (el: Element) =>
      el.matches('img, video, picture, [role="img"]') ||
      getComputedStyle(el).backgroundImage.includes('url(')
    const isGradient = (el: Element) => getComputedStyle(el).backgroundImage.includes('gradient(')
    return [...document.querySelectorAll('body *')].filter((el) => {
      const r = el.getBoundingClientRect()
      if (r.top >= fold) return false
      // A real image or video of real size, not a small icon.
      if (isImage(el)) return r.width >= 80 && r.height >= 80
      // A colored gradient as a placeholder, large enough to stand in for a
      // hero image. A plain colored shape with an icon in it does not count.
      if (isGradient(el)) return r.width >= 200 && r.height >= 150
      return false
    }).length
  })
}

// Menu items are counted by their visible prices, such as ₹120, Rs 80 or $4.50.
async function visiblePriceCount(page: Page): Promise<number> {
  return page.evaluate(() => {
    const price = /(₹|rs\.?|inr|\$|€|£)\s?\d|\d\s?(₹|\/-)/i
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    let count = 0
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement
      if (parent && price.test(node.textContent ?? '') && parent.checkVisibility()) count++
    }
    return count
  })
}

const SUBMIT = /send|submit|order|contact|enquir/i
const SUCCESS =
  /thank|sent|received|submitted|success|we('|’)?ll (get back|be in touch|contact)|we will (get back|be in touch|contact)/i
const ERROR_TEXT =
  /required|please (enter|fill|provide|add)|invalid|not valid|can('|’)?t be (empty|blank)|cannot be (empty|blank)/i

// The submit button: one inside a <form> if there is one. Otherwise the last
// matching button, since a "Contact" button in the header comes first.
async function submitButton(page: Page): Promise<Locator> {
  const inForm = page.locator('form').getByRole('button', { name: SUBMIT })
  if ((await inForm.count()) > 0) return inForm.first()
  return page.getByRole('button', { name: SUBMIT }).last()
}

// The form around the submit button: its <form>, or its section when the
// app has no <form> tag.
async function formScope(page: Page): Promise<Locator> {
  const button = await submitButton(page)
  for (const ancestor of ['form', 'section']) {
    const scope = button.locator(`xpath=ancestor::${ancestor}[1]`)
    if ((await scope.count()) > 0) return scope
  }
  return page.locator('body')
}

// Fill every field in the form with a value that should be accepted.
async function fillValid(scope: Locator) {
  const fields = scope.locator(
    'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=radio]), textarea, select',
  )
  for (const field of await fields.all()) {
    if (!(await field.isVisible())) continue
    const info = await field.evaluate((el: HTMLInputElement) => ({
      tag: el.tagName.toLowerCase(),
      type: (el.getAttribute('type') ?? 'text').toLowerCase(),
      hint: [
        el.name,
        el.id,
        el.placeholder,
        el.getAttribute('aria-label') ?? '',
        ...[...(el.labels ?? [])].map((l) => l.textContent ?? ''),
      ]
        .join(' ')
        .toLowerCase(),
    }))

    if (info.tag === 'select') {
      const values = await field.locator('option').evaluateAll((opts) =>
        (opts as HTMLOptionElement[]).map((o) => o.value).filter(Boolean),
      )
      if (values.length) await field.selectOption(values[0])
    } else if (info.type === 'checkbox') {
      await field.check()
    } else if (info.type === 'email' || /e-?mail/.test(info.hint)) {
      await field.fill('asha@example.com')
    } else if (info.type === 'tel' || /phone|mobile/.test(info.hint)) {
      await field.fill('9876543210')
    } else if (info.type === 'number' || /quantity|qty|how many/.test(info.hint)) {
      await field.fill('2')
    } else if (info.type === 'date') {
      await field.fill('2026-12-01')
    } else if (info.tag === 'textarea' || /message|note|details/.test(info.hint)) {
      await field.fill('Two dozen croissants for Saturday morning, please.')
    } else {
      await field.fill('Asha Rao')
    }
  }
}

// An error is shown when a field is marked invalid, an alert or error text
// appears, or the browser's own validation blocks the submit.
async function showsValidationError(scope: Locator): Promise<boolean> {
  return scope.evaluate((root, errorSource) => {
    const errorText = new RegExp(errorSource, 'i')
    const visible = (el: Element) => (el as HTMLElement).checkVisibility()
    const fields = [...root.querySelectorAll('input, textarea, select')] as HTMLInputElement[]

    if (fields.some((f) => f.getAttribute('aria-invalid') === 'true')) return true
    // Browser validation only blocks the submit when the form allows it.
    if (fields.some((f) => !f.validity.valid && !f.form?.noValidate)) return true
    const alerts = [...document.querySelectorAll('[role="alert"]')]
    if (alerts.some((a) => visible(a) && (a.textContent ?? '').trim())) return true

    // Labels like "Name (required)" are not errors, so leave them out.
    const copy = root.cloneNode(true) as Element
    copy.querySelectorAll('label').forEach((l) => l.remove())
    return errorText.test(copy.textContent ?? '')
  }, ERROR_TEXT.source)
}

// The form's email field, or null when the form asks only for a phone.
async function emailField(scope: Locator): Promise<Locator | null> {
  const typed = scope.locator('input[type=email]')
  if ((await typed.count()) > 0) return typed.first()
  const labelled = scope.getByLabel(/e-?mail/i)
  if ((await labelled.count()) > 0) return labelled.first()
  return null
}

// Success text the page already shows before submitting, such as "We'll get
// back to you within a day", must not count as a confirmation.
async function successCount(page: Page): Promise<number> {
  return page.getByText(SUCCESS).count()
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('shows the bakery name at the top of the page', async ({ page }) => {
    const candidates = await bakeryNameCandidates(page)
    const names = candidates.filter(looksLikeName)
    expect(names, `no bakery name at the top; found ${JSON.stringify(candidates)}`).not.toHaveLength(0)
  })

  test('opens with a hero image, video or gradient placeholder', async ({ page }) => {
    expect(await heroMediaCount(page)).toBeGreaterThanOrEqual(1)
  })

  test('shows a menu with at least 3 items', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /menu/i }).first()).toBeVisible()
    expect(await visiblePriceCount(page)).toBeGreaterThanOrEqual(3)
  })

  test('has a contact form', async ({ page }) => {
    await expect(page.getByLabel(/email|phone|mobile/i).first()).toBeVisible()
    await expect(await submitButton(page)).toBeVisible()
  })

  test('contact form rejects an empty submission', async ({ page }) => {
    const scope = await formScope(page)
    const before = await successCount(page)
    await (await submitButton(page)).click()

    await expect.poll(() => showsValidationError(scope)).toBe(true)
    expect(await successCount(page)).toBe(before)
  })

  test('contact form rejects a badly formatted email', async ({ page }) => {
    const scope = await formScope(page)
    const email = await emailField(scope)
    test.skip(!email, 'Form has no email field')

    const before = await successCount(page)
    await fillValid(scope)
    await email!.fill('not-an-email')
    await (await submitButton(page)).click()

    await expect.poll(() => showsValidationError(scope)).toBe(true)
    expect(await successCount(page)).toBe(before)
  })

  test('contact form accepts a valid submission', async ({ page }) => {
    const scope = await formScope(page)
    const before = await successCount(page)
    await fillValid(scope)
    await (await submitButton(page)).click()

    await expect.poll(() => successCount(page)).toBeGreaterThan(before)
  })
})
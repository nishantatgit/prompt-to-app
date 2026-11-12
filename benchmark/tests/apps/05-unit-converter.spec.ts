import { test, expect, type Locator, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: km/miles, kg/lb and Celsius/Fahrenheit all convert correctly in
// both directions, and non-numeric input is refused.
//
// Converters are built in many shapes, so the test supports the common ones:
// - a pair of fields per unit, where typing in one fills the other
// - one field with "from" and "to" dropdowns
// - one field per conversion with a swap button
// - one field with a single direction dropdown or radio, like "Kilometers to Miles"
// A category tab or button (Distance, Weight, Temperature) is clicked first
// when the page has one.
// The answer is found by looking for the expected number anywhere on the
// page, not in a specific element, as the tip calculator spec does.

const app = getApp(5)
const url = getAppUrl(app.id)

// label: how a field, dropdown option or heading names the unit.
// mention: how page text names it, stricter so a stray letter C does not count.
type Unit = { name: string; label: RegExp; mention: RegExp; category: RegExp }

const KM: Unit = { name: 'km', label: /\bkm\b|kilomet/i, mention: /\bkm\b|kilomet/i, category: /length|distance/i }
const MI: Unit = { name: 'miles', label: /\bmi\b|miles?/i, mention: /\bmi\b|miles?/i, category: /length|distance/i }
const KG: Unit = { name: 'kg', label: /\bkg\b|kilogra/i, mention: /\bkg\b|kilogra/i, category: /weight|mass/i }
const LB: Unit = { name: 'lb', label: /\blbs?\b|pounds?/i, mention: /\blbs?\b|pounds?/i, category: /weight|mass/i }
const C: Unit = { name: '°C', label: /celsius|°\s?c\b|\(c\)|^c$/i, mention: /celsius|°\s?c\b/i, category: /temp/i }
const F: Unit = { name: '°F', label: /fahrenheit|°\s?f\b|\(f\)|^f$/i, mention: /fahrenheit|°\s?f\b/i, category: /temp/i }

const SWAP = /swap|reverse|switch|flip|⇄|↔|⇆/i
const CONVERT = /^(convert|calculate)\b/i
const ERROR_TEXT = /invalid|valid number|not a number|numbers? only|must be a number/i

// Inputs and expected outputs. Values are picked so the answer is unlikely to
// appear on the page by chance.
const CASES: [Unit, Unit, number, number][] = [
  [KM, MI, 42, 26.0976],
  [MI, KM, 26.2, 42.1648],
  [KG, LB, 70, 154.324],
  [LB, KG, 150, 68.0389],
  [C, F, 37, 98.6],
  [F, C, 451, 232.778],
]

function numberField(scope: Page | Locator, name: RegExp): Locator {
  return scope
    .getByRole('spinbutton', { name })
    .or(scope.getByRole('textbox', { name }))
    .first()
}

async function visible(locator: Locator): Promise<boolean> {
  return (await locator.count()) > 0 && (await locator.first().isVisible())
}

// Pick the dropdown option whose text matches the unit (or category).
async function selectUnit(select: Locator, unit: { label: RegExp }): Promise<boolean> {
  const value = await select.evaluate((el: HTMLSelectElement, source) => {
    const re = new RegExp(source, 'i')
    const option = [...el.options].find((o) => re.test(o.textContent ?? '') || re.test(o.value))
    return option ? option.value : null
  }, unit.label.source)
  if (value === null) return false
  await select.selectOption(value)
  return true
}

// Get the page ready to convert `from` into `to` and return the field to type
// into, or null when the page offers no way to do it.
async function prepare(page: Page, from: Unit, to: Unit): Promise<Locator | null> {
  // A tab or button for the category, such as "Temperature".
  const tab = page
    .getByRole('tab', { name: from.category })
    .or(page.getByRole('button', { name: from.category }))
    .first()
  if (await visible(tab)) await tab.click()

  // Shape 1 and 3: a field labelled with the "from" unit.
  let field = numberField(page, from.label)
  if (await visible(field)) return field

  // Shape 3: a swap button turns the "to" field into the "from" field.
  if (await visible(numberField(page, to.label))) {
    for (const swap of await page.getByRole('button', { name: SWAP }).all()) {
      if (!(await swap.isVisible())) continue
      await swap.click()
      field = numberField(page, from.label)
      if (await visible(field)) return field
      await swap.click()
    }
  }

  // Shape 2: "from" and "to" dropdowns next to one field, sometimes after
  // a category dropdown.
  const selects = await page.locator('select').all()
  for (const select of selects) await selectUnit(select, { label: from.category })
  for (let i = 0; i < selects.length; i++) {
    for (let j = 0; j < selects.length; j++) {
      if (i === j) continue
      if (!(await selectUnit(selects[i], from))) continue
      if (!(await selectUnit(selects[j], to))) continue
      const box = selects[i].locator('xpath=ancestor::*[.//input][1]')
      const input = box.locator('input:not([type=hidden]):not([type=checkbox]):not([type=radio])')
      if (await visible(input)) return input.first()
    }
  }
  // Shape 4: one direction choice such as "Kilometers to Miles", as a
  // dropdown option or a radio button, next to one field.
  for (const select of selects) {
    const value = await select.evaluate(
      (el: HTMLSelectElement, [fromSource, toSource]) => {
        const from = new RegExp(fromSource, 'i')
        const to = new RegExp(toSource, 'i')
        const option = [...el.options].find((o) => {
          const text = o.textContent ?? ''
          const a = text.search(from)
          const b = text.search(to)
          return a >= 0 && b > a
        })
        return option ? option.value : null
      },
      [from.label.source, to.label.source],
    )
    if (value === null) continue
    await select.selectOption(value)
    const box = select.locator('xpath=ancestor::*[.//input][1]')
    const input = box.locator('input:not([type=hidden]):not([type=checkbox]):not([type=radio])')
    if (await visible(input)) return input.first()
  }
  const direction = new RegExp(`(${from.label.source}).*\\bto\\b.*(${to.label.source})`, 'i')
  const radio = page.getByRole('radio', { name: direction }).first()
  if (await visible(radio)) {
    await radio.check()
    const input = page.getByRole('spinbutton').or(page.getByRole('textbox')).first()
    if (await visible(input)) return input
  }
  return null
}

async function typeValue(page: Page, field: Locator, value: string) {
  await field.fill(value)
  const convert = page.getByRole('button', { name: CONVERT }).first()
  if (await visible(convert)) await convert.click()
}

// Every number shown on the page, in text and in fields, except the field
// the test typed into.
async function shownNumbers(page: Page, typed: Locator): Promise<number[]> {
  await typed.evaluate((el) => el.setAttribute('data-bench-typed', ''))
  return page.evaluate(() => {
    const found: string[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const parent = n.parentElement
      if (parent && parent.closest('option, script, style') === null && parent.checkVisibility()) {
        found.push(n.textContent ?? '')
      }
    }
    for (const el of document.querySelectorAll('input, output, textarea')) {
      if (el.hasAttribute('data-bench-typed')) continue
      found.push((el as HTMLInputElement).value ?? el.textContent ?? '')
    }
    const numbers = found.join(' ').replace(/,/g, '').match(/[-−]?\d+(\.\d+)?/g) ?? []
    return numbers.map((s) => Number(s.replace('−', '-')))
  })
}

// Rounded answers like 26.1 or 98.6 count; a wrong formula does not.
function close(actual: number, expected: number): boolean {
  return Math.abs(actual - expected) <= Math.max(0.05, Math.abs(expected) * 0.002)
}

async function expectConversion(page: Page, from: Unit, to: Unit, input: number, expected: number) {
  const field = await prepare(page, from, to)
  expect(field, `no way to convert ${from.name} to ${to.name}`).not.toBeNull()

  await typeValue(page, field!, String(input))
  await expect
    .poll(async () => (await shownNumbers(page, field!)).some((n) => close(n, expected)), {
      message: `${input} ${from.name} should show about ${expected} ${to.name}`,
    })
    .toBe(true)
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('offers all three conversions', async ({ page }) => {
    const pageText = () =>
      page.locator('body').evaluate((body) => {
        const labels = [...body.querySelectorAll('[aria-label], [placeholder]')].map(
          (el) => `${el.getAttribute('aria-label') ?? ''} ${el.getAttribute('placeholder') ?? ''}`,
        )
        return `${body.textContent ?? ''} ${labels.join(' ')}`
      })

    // A page with category tabs shows one category at a time, so open each.
    let text = await pageText()
    for (const category of [KM.category, KG.category, C.category]) {
      const tab = page
        .getByRole('tab', { name: category })
        .or(page.getByRole('button', { name: category }))
        .first()
      if (await visible(tab)) {
        await tab.click()
        text += ' ' + (await pageText())
      }
    }
    for (const unit of [KM, MI, KG, LB, C, F]) {
      expect(text, `mentions ${unit.name}`).toMatch(unit.mention)
    }
  })

  for (const [from, to, input, expected] of CASES) {
    test(`converts ${from.name} to ${to.name}`, async ({ page }) => {
      await expectConversion(page, from, to, input, expected)
    })
  }

  test('converts a negative temperature', async ({ page }) => {
    await expectConversion(page, C, F, -40, -40)
  })

  test('refuses non-numeric input', async ({ page }) => {
    const field = await prepare(page, KM, MI)
    expect(field, 'no way to convert km to miles').not.toBeNull()

    // A number field refuses letters outright, and Playwright reports that.
    const refused = await typeValue(page, field!, 'abc').then(
      () => false,
      () => true,
    )
    await expect(page.getByText(/\bnan\b|infinity/i)).toHaveCount(0)
    if (refused) return

    const kept = await field!.inputValue()
    const flagged = await field!.evaluate((el, source) => {
      const errorText = new RegExp(source, 'i')
      if (el.getAttribute('aria-invalid') === 'true') return true
      const alerts = [...document.querySelectorAll('[role="alert"]')]
      if (alerts.some((a) => (a as HTMLElement).checkVisibility() && a.textContent?.trim())) return true
      return errorText.test(document.body.innerText)
    }, ERROR_TEXT.source)

    expect(kept === '' || flagged, 'letters were accepted without an error').toBe(true)
  })
})
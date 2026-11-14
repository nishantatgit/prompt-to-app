import { expect, type Browser, type Locator, type Page } from '@playwright/test'

// Shared checks for apps that save data on a server (level 3 and up).
//
// The check that tells server storage apart from browser storage is a second
// browser: it has its own storage, so it only sees data the app saved on a
// server.

// An input field (text, email, number or slider) whose label matches.
export function field(page: Page, name: RegExp): Locator {
  return page
    .getByRole('textbox', { name })
    .or(page.getByRole('spinbutton', { name }))
    .first()
}

export function button(scope: Page | Locator, name: RegExp): Locator {
  return scope.getByRole('button', { name }).first()
}

// Shown text, never the value of an input or textarea: text still typed into
// a field would otherwise match before anything was saved.
export function shown(page: Page, text: string): Locator {
  return page.getByText(text).and(page.locator(':not(textarea):not(input)')).first()
}

export function unique(label: string): string {
  return `${label} ${Date.now().toString().slice(-6)}${Math.floor(Math.random() * 1000)}`
}

export function uniqueEmail(): string {
  return `bench${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`
}

// Fill a field only when the app has one, such as an optional email.
export async function fillIfPresent(page: Page, name: RegExp, value: string) {
  const input = field(page, name)
  if ((await input.count()) > 0 && (await input.isVisible())) await input.fill(value)
}

// Open the app in a fresh browser with its own storage and run `check` there.
export async function asAnotherVisitor(
  browser: Browser,
  url: string,
  check: (page: Page) => Promise<void>,
) {
  const context = await browser.newContext()
  try {
    const page = await context.newPage()
    await page.goto(url)
    await check(page)
  } finally {
    await context.close()
  }
}

// The text of the smallest element around `text` that holds one whole item,
// such as a list row or card: it climbs from the text while the parent does
// not also hold one of `others` (the names of other items on the page).
export async function itemText(page: Page, text: string, others: string[] = []): Promise<string> {
  await expect(shown(page, text)).toBeVisible({ timeout: 10_000 })
  return shown(page, text).evaluate(
    (el, others) => {
      let node: Element = el
      for (let i = 0; i < 6 && node.parentElement; i++) {
        const parent = node.parentElement
        const holds = parent.textContent ?? ''
        if (parent.tagName === 'BODY' || parent.tagName === 'MAIN') break
        if (others.some((o) => holds.includes(o))) break
        if (parent.querySelectorAll('li, tr, article, [role="listitem"], [role="row"]').length > 1) break
        node = parent
        if (['LI', 'TR', 'ARTICLE'].includes(node.tagName)) break
        const role = node.getAttribute('role')
        if (role === 'listitem' || role === 'row') break
      }
      return node.textContent ?? ''
    },
    others,
  )
}

// The element that holds one whole item, for clicking buttons inside it.
export function itemLocator(page: Page, text: string): Locator {
  return page
    .locator('li, tr, article, [role="listitem"], [role="row"], div')
    .filter({ has: shown(page, text) })
    .filter({ has: page.getByRole('button').or(page.getByRole('checkbox')) })
    .last()
}

export function numbersIn(text: string): number[] {
  return (text.match(/\d+/g) ?? []).map(Number)
}

import { test, expect } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'

// Pass check: the portfolio names its owner and has separate work and
// contact sections, with at least one way to get in touch.
//
// "Page is not empty" and "responsive" are already covered by the common
// checks (page loads, fits a mobile screen), so they are not repeated here.
//
// Section checks look for headings, not <section> tags, so the test works
// however the agent structures the markup.

const app = getApp(1)
const url = getAppUrl(app.id)

// Headings that are page labels, not a person's name.
const GENERIC_TITLE = /^(my )?(portfolio|welcome|home|about( me)?|hello|hi)!?$/i

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('shows the person name as the main heading', async ({ page }) => {
    const h1 = page.getByRole('heading', { level: 1 }).first()
    await expect(h1).toBeVisible()

    const name = (await h1.innerText()).trim()
    expect(name.length).toBeGreaterThan(1)
    expect(name).not.toMatch(GENERIC_TITLE)
  })

  test('has more than one section', async ({ page }) => {
    const sectionHeadings = page.getByRole('heading', { level: 2 })
    expect(await sectionHeadings.count()).toBeGreaterThanOrEqual(2)
  })

  test('has a work section', async ({ page }) => {
    const work = page.getByRole('heading', { name: /projects?|work|experience|case stud/i })
    await expect(work.first()).toBeVisible()
  })

  test('has contact details', async ({ page }) => {
    const contact = page.getByRole('heading', { name: /contact|get in touch|reach me/i })
    await expect(contact.first()).toBeVisible()

    // A contact link or a plain-text email address both count.
    const contactLinks = page.locator(
      'a[href^="mailto:"], a[href^="tel:"], a[href*="linkedin.com"], a[href*="github.com"], a[href*="x.com"], a[href*="twitter.com"]',
    )
    const plainEmail = page.getByText(/[\w.+-]+@[\w-]+\.[\w.-]+/)
    const ways = (await contactLinks.count()) + (await plainEmail.count())
    expect(ways).toBeGreaterThanOrEqual(1)
  })
})
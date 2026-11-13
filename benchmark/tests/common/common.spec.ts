import { test, expect, type Page } from '@playwright/test'
import { apps, getAppUrl, tagsFor } from '../../helpers/apps'
import {
  MIN_CONTRAST,
  contrast,
  isNeutral,
  paletteProblems,
  parseColor,
  type RGB,
} from '../../helpers/colors'

type Chart = { colors: RGB[]; background: RGB }

// Charts drawn as SVG: an svg of at least 200 by 120 px with three or more
// shapes, so icons do not count. Series colors are the shapes' fills and
// strokes, minus grays (axes, gridlines, text). Canvas charts are not read.
async function readCharts(page: Page): Promise<Chart[]> {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000) // let chart animations settle
  const raw = await page.evaluate(() => {
    const shapes = 'rect, path, circle, ellipse, line, polyline, polygon'
    return [...document.querySelectorAll('svg')]
      .filter((svg) => {
        const r = svg.getBoundingClientRect()
        return r.width >= 200 && r.height >= 120 && svg.querySelectorAll(shapes).length >= 3
      })
      .map((svg) => {
        const colors = [...svg.querySelectorAll(shapes)].flatMap((el) => {
          const style = getComputedStyle(el)
          return [style.fill, style.stroke]
        })
        let background = 'rgb(255, 255, 255)'
        for (let el: Element | null = svg; el; el = el.parentElement) {
          const bg = getComputedStyle(el).backgroundColor
          if (bg && !/rgba\(.*,\s*0\)|transparent/.test(bg)) {
            background = bg
            break
          }
        }
        return { colors, background }
      })
  })
  return raw.map(({ colors, background }) => {
    const series: RGB[] = []
    for (const css of colors) {
      const rgb = parseColor(css)
      if (!rgb || isNeutral(rgb)) continue
      if (!series.some((s) => s.every((v, i) => Math.abs(v - rgb[i]) < 2))) series.push(rgb)
    }
    return { colors: series, background: parseColor(background) ?? [255, 255, 255] }
  })
}

const describe = (p: { a: string; b?: string; check: string; value: number; needed: number }) =>
  `${p.a}${p.b ? ' vs ' + p.b : ''}: ${p.check} ${p.value.toFixed(1)}, needs ${p.needed}`

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

    // Two or more series colors in a chart must look different, also to
    // people with protanopia, deuteranopia or tritanopia.
    test('chart colors can be told apart', async ({ page }) => {
      await page.goto(url!)
      const charts = (await readCharts(page)).filter((c) => c.colors.length >= 2)
      test.skip(charts.length === 0, 'No chart with two or more colors')
      const problems = charts.flatMap((c) =>
        paletteProblems(c.colors, c.background).filter((p) => p.b),
      )
      expect(problems.map(describe)).toEqual([])
    })

    // Every series color stands out from the chart's background (WCAG 3:1).
    // Reported only, never a failure: many good palettes, Okabe-Ito among
    // them, have a color below 3:1 on white. Weak colors show up as an
    // annotation on this test in the report.
    test('chart colors stand out from the background (reported only)', async ({ page }) => {
      await page.goto(url!)
      const charts = (await readCharts(page)).filter((c) => c.colors.length >= 1)
      test.skip(charts.length === 0, 'No chart')
      const weak = charts.flatMap((c) =>
        c.colors
          .map((color) => ({ color, ratio: contrast(color, c.background) }))
          .filter((x) => x.ratio < MIN_CONTRAST),
      )
      for (const w of weak) {
        test.info().annotations.push({
          type: 'weak chart contrast',
          description: `rgb(${w.color.join(', ')}): ${w.ratio.toFixed(2)}:1, needs ${MIN_CONTRAST}:1`,
        })
      }
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

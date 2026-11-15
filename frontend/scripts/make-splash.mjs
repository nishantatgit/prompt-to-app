// Renders the iOS startup images into public/splash and prints the <link> tags
// for index.html. Run with: node scripts/make-splash.mjs
// Android needs none of this: it draws its splash from site.webmanifest.
// Set SPLASH_FONT to a local Unbounded 700 .woff2 file to render offline.
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'

const { chromium } = createRequire(import.meta.url)('playwright')
const localFont = process.env.SPLASH_FONT

// CSS width, height and pixel ratio of each iPhone and iPad screen, portrait.
const DEVICES = [
  [440, 956, 3], [402, 874, 3], [430, 932, 3], [393, 852, 3], [428, 926, 3],
  [390, 844, 3], [375, 812, 3], [414, 896, 3], [414, 896, 2], [414, 736, 3],
  [375, 667, 2], [320, 568, 2],
  [1024, 1366, 2], [834, 1210, 2], [834, 1194, 2], [820, 1180, 2], [834, 1112, 2],
  [810, 1080, 2], [768, 1024, 2], [744, 1133, 2],
]

const page_url = new URL('./splash-screen.html', import.meta.url).href
const out = fileURLToPath(new URL('../public/splash/', import.meta.url))
const browser = await chromium.launch()
const tags = []
for (const [w, h, dpr] of DEVICES) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dpr })
  if (localFont) await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort())
  await page.goto(page_url, { waitUntil: 'load' })
  if (localFont) {
    const src = pathToFileURL(localFont).href
    await page.addStyleTag({ content: `@font-face { font-family: 'Unbounded'; font-weight: 700; src: url('${src}'); }` })
  }
  const loaded = await page.evaluate(() => document.fonts.load("700 40px 'Unbounded'").then((f) => f.length))
  if (!loaded) throw new Error('Unbounded did not load; set SPLASH_FONT')
  const name = `splash-${w * dpr}x${h * dpr}.png`
  await page.screenshot({ path: out + name })
  await page.close()
  tags.push(
    `    <link rel="apple-touch-startup-image" href="/splash/${name}" media="(device-width: ${w}px) and (device-height: ${h}px) and (-webkit-device-pixel-ratio: ${dpr}) and (orientation: portrait)" />`,
  )
}
await browser.close()
console.log(tags.join('\n'))

// Takes a phone sized photo of a deployed app, for the end of the build
// animation. Run from an app's workspace, so Playwright comes from that
// app's own node_modules (the same one its tests use):
//   node screenshot.cjs <url> <out.jpg>
const { chromium } = require(require.resolve("@playwright/test", { paths: [process.cwd()] }));

const [url, out] = process.argv.slice(2);
// The same shape as the photo in the animation, at twice the pixels.
const VIEWPORT = { width: 390, height: 465 };

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 2 });
    try {
      await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
    } catch {
      // An app that keeps a connection open (live chat) never goes idle;
      // what has loaded by now is enough for a photo.
    }
    if (page.url() === "about:blank") throw new Error(`could not open ${url}`);
    await page.waitForTimeout(800); // let entrance animations settle
    await page.screenshot({ path: out, type: "jpeg", quality: 72 });
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(String(error));
  process.exit(1);
});

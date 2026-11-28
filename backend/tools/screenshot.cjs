// Takes a phone sized photo of a deployed app, for the end of the build
// animation. Run from an app's workspace, so Playwright comes from that
// app's own node_modules (the same one its tests use):
//   node screenshot.cjs <url> <out.jpg>
const { chromium } = require(require.resolve("@playwright/test", { paths: [process.cwd()] }));

const [url, out] = process.argv.slice(2);
// The same shape as the photo in the animation, at twice the pixels.
const VIEWPORT = { width: 390, height: 465 };
// The app's domain is attached just before this runs, so for a few seconds it
// can answer with Vercel's 404 page or not answer at all. Try a few times,
// and never save a photo of an error page as the app.
const ATTEMPTS = 3;
const RETRY_MS = Number(process.env.SCREENSHOT_RETRY_MS) || 4000;

// Opens url and returns the status of the page itself (after redirects), or
// null when nothing answered.
async function open(page) {
  let status = null;
  const onResponse = (response) => {
    if (response.request().isNavigationRequest() && response.frame() === page.mainFrame()) {
      status = response.status();
    }
  };
  page.on("response", onResponse);
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
  } catch {
    // An app that keeps a connection open (live chat) never goes idle;
    // what has loaded by now is enough for a photo.
  } finally {
    page.off("response", onResponse);
  }
  return status;
}

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 2 });
    let status = null;
    for (let attempt = 1; attempt <= ATTEMPTS; attempt++) {
      status = await open(page);
      if (status !== null && status < 400) break;
      if (attempt < ATTEMPTS) await page.waitForTimeout(RETRY_MS);
    }
    if (status === null) throw new Error(`could not open ${url}`);
    if (status >= 400) throw new Error(`${url} answered ${status}, not photographing an error page`);
    await page.waitForTimeout(800); // let entrance animations settle
    await page.screenshot({ path: out, type: "jpeg", quality: 72 });
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(String(error));
  process.exit(1);
});

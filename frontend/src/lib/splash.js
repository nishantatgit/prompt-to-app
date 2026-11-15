// The splash in index.html covers the installed app while it loads. Once the
// first screen is drawn it fades out, after a short minimum so it never just
// flickers past.
const MIN_SHOWN_MS = 600
const FADE_MS = 250

export function hideSplash() {
  const splash = document.getElementById('splash')
  if (!splash) return
  const wait = Math.max(0, MIN_SHOWN_MS - performance.now())
  setTimeout(() => {
    splash.classList.add('splash-hide')
    // Removed after the fade; with reduced motion there is no fade to wait for.
    setTimeout(() => splash.remove(), FADE_MS)
  }, wait)
}

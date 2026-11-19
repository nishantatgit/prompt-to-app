// Whether Vyskar is running inside its Android app (a Trusted Web Activity).
// The app opens /?source=android; Chrome also sets the referrer to
// android-app://com.vyskar.app on launch. Remembered for the session, since
// the query string is gone after the first page.
//
// Inside the Android app, Google Play's billing rules apply to buying
// builds, so the app hides buying and links to paid packs.
const KEY = 'vyskar.platform'

function detect() {
  try {
    if (sessionStorage.getItem(KEY) === 'android') return true
  } catch {
    // no storage: fall through to the signals on this page
  }
  const fromQuery = new URLSearchParams(window.location.search).get('source') === 'android'
  const fromReferrer = document.referrer.startsWith('android-app://com.vyskar.app')
  if (fromQuery || fromReferrer) {
    try {
      sessionStorage.setItem(KEY, 'android')
    } catch {
      // the check above repeats on the next page
    }
    return true
  }
  return false
}

export const inAndroidApp = detect()

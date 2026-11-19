# Vyskar for Android

The Play Store app is app.vyskar.com in a Trusted Web Activity: Chrome shows
the site full screen, with no browser bar. Nothing here duplicates the web
app; every web release reaches Android at once.

## Build

Run the **Android app** workflow on GitHub (Actions, Android app, Run
workflow). It generates the project from `twa-manifest.json`, builds it, and
attaches:

- `vyskar.aab`: upload this to Play Console
- `vyskar.apk`: install on a phone to try it
- `fingerprints.txt`: the signing key's SHA-256 fingerprint

Bump `appVersionCode` (and `appVersionName`) in `twa-manifest.json` for every
upload to Play Console.

## Signing key

Without secrets, the workflow signs with a throwaway key: fine for trying the
APK, not for Play Console. For Play Console, create an upload key once on your
Mac and add it as GitHub secrets:

    keytool -genkeypair -v -keystore upload-key.jks -alias upload \
      -keyalg RSA -keysize 2048 -validity 10000
    base64 -i upload-key.jks | gh secret set ANDROID_UPLOAD_KEY_BASE64
    gh secret set ANDROID_UPLOAD_KEY_PASSWORD

Keep `upload-key.jks` and its password safe, outside the repo.

## Digital Asset Links

Chrome hides the browser bar only when app.vyskar.com vouches for the app, in
`frontend/public/.well-known/assetlinks.json`. It needs the SHA-256
fingerprints of the upload key (from `fingerprints.txt`) and of Google's app
signing key (Play Console, Setup, App signing).

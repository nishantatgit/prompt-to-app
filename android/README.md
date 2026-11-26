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

Chrome hides the browser bar only when app.vyskar.com vouches for the app at
`/.well-known/assetlinks.json`. That file is not in the repo yet: until it
is, the Play Store app opens app.vyskar.com with a browser bar on top.

It needs the SHA-256 fingerprints of the upload key and of Google's app
signing key (Play Console, Setup, App signing). The workflow writes it for
you:

1. Run the **Android app** workflow with the upload key secrets set, and paste
   Google's app signing SHA-256 into the `play_signing_sha256` box.
2. Take `assetlinks.json` from the run's files and commit it as
   `frontend/public/.well-known/assetlinks.json`.
3. Once Vercel has deployed it, check
   https://app.vyskar.com/.well-known/assetlinks.json opens.

Do not commit one made with the throwaway key: it vouches for an app nobody
installs. To make the file by hand: `node assetlinks.mjs fingerprints.txt
<play SHA-256>`.

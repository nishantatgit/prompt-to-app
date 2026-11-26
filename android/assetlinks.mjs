// Writes the Digital Asset Links file that app.vyskar.com must serve at
// /.well-known/assetlinks.json. Chrome only hides the browser bar in the
// Play Store app when the site lists the app's signing key fingerprints.
//
//   node assetlinks.mjs fingerprints.txt [extra SHA-256 ...] > assetlinks.json
//
// fingerprints.txt is keytool's output (lines like "SHA256: AB:CD:..."). Extra
// fingerprints, such as Google's app signing key from Play Console, can be
// given with or without colons.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

// A SHA-256 fingerprint: 32 bytes as hex, with or without colons.
const FINGERPRINT = /\b(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}\b|\b[0-9A-Fa-f]{64}\b/g

export function normalize(fingerprint) {
  const hex = fingerprint.replace(/:/g, '').toUpperCase()
  if (!/^[0-9A-F]{64}$/.test(hex)) {
    throw new Error(`Not a SHA-256 fingerprint: ${fingerprint}`)
  }
  return hex.match(/../g).join(':')
}

export function findFingerprints(text) {
  return (text.match(FINGERPRINT) || []).map(normalize)
}

export function assetLinks(packageName, fingerprints) {
  const unique = [...new Set(fingerprints.map(normalize))]
  if (unique.length === 0) throw new Error('No SHA-256 fingerprints given.')
  return [
    {
      relation: ['delegate_permission/common.handle_all_urls'],
      target: {
        namespace: 'android_app',
        package_name: packageName,
        sha256_cert_fingerprints: unique,
      },
    },
  ]
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [file, ...extra] = process.argv.slice(2)
  if (!file) {
    console.error('Usage: node assetlinks.mjs fingerprints.txt [extra SHA-256 ...]')
    process.exit(1)
  }
  const manifest = JSON.parse(readFileSync(new URL('./twa-manifest.json', import.meta.url), 'utf8'))
  const fingerprints = [...findFingerprints(readFileSync(file, 'utf8')), ...extra.filter(Boolean)]
  console.log(JSON.stringify(assetLinks(manifest.packageId, fingerprints), null, 2))
}

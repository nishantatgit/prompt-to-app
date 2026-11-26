import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

import { assetLinks, findFingerprints, normalize } from './assetlinks.mjs'

const UPLOAD = 'AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89'
const PLAY = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'

test('reads the fingerprint from keytool output', () => {
  const keytool = `Certificate fingerprints:\nSHA1: 11:22:33:44:55:66:77:88:99:00:AA:BB:CC:DD:EE:FF:11:22:33:44\nSHA256: ${UPLOAD}\n`
  assert.deepEqual(findFingerprints(keytool), [UPLOAD])
})

test('accepts a fingerprint without colons, in any case', () => {
  assert.equal(normalize(PLAY), PLAY.toUpperCase().match(/../g).join(':'))
})

test('refuses something that is not a SHA-256 fingerprint', () => {
  assert.throws(() => normalize('AB:CD'), /Not a SHA-256 fingerprint/)
})

test('lists each key once for the app', () => {
  const [statement] = assetLinks('com.vyskar.app', [UPLOAD, UPLOAD.toLowerCase(), PLAY])
  assert.deepEqual(statement.relation, ['delegate_permission/common.handle_all_urls'])
  assert.equal(statement.target.namespace, 'android_app')
  assert.equal(statement.target.package_name, 'com.vyskar.app')
  assert.deepEqual(statement.target.sha256_cert_fingerprints, [UPLOAD, normalize(PLAY)])
})

test('refuses to write a file with no keys', () => {
  assert.throws(() => assetLinks('com.vyskar.app', []), /No SHA-256 fingerprints/)
})

test('the command uses the package from twa-manifest.json', () => {
  const dir = mkdtempSync(join(tmpdir(), 'assetlinks-'))
  const file = join(dir, 'fingerprints.txt')
  writeFileSync(file, `SHA256: ${UPLOAD}\n`)
  const script = fileURLToPath(new URL('./assetlinks.mjs', import.meta.url))
  const out = JSON.parse(execFileSync('node', [script, file, PLAY, ''], { encoding: 'utf8' }))
  assert.equal(out[0].target.package_name, 'com.vyskar.app')
  assert.equal(out[0].target.sha256_cert_fingerprints.length, 2)
})

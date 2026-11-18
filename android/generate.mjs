// Generates the Android project for Vyskar's Play Store app from
// twa-manifest.json, without Bubblewrap's interactive prompts, so it runs on
// GitHub Actions. The app opens app.vyskar.com full screen in Chrome (a
// Trusted Web Activity): every web release reaches it at once.
//
//   node generate.mjs build/project
import { ConsoleLog, TwaGenerator, TwaManifest } from '@bubblewrap/core'
import { resolve } from 'node:path'

const target = resolve(process.argv[2] || 'build/project')
const manifest = await TwaManifest.fromFile(new URL('./twa-manifest.json', import.meta.url).pathname)

const problem = manifest.validate()
if (problem) {
  console.error(`twa-manifest.json: ${problem}`)
  process.exit(1)
}

await new TwaGenerator().createTwaProject(target, manifest, new ConsoleLog('generate'))
console.log(`Android project written to ${target}`)

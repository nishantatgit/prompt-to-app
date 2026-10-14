import fs from 'node:fs'
import path from 'node:path'

export type BenchmarkApp = {
  id: number
  slug: string
  level: number
  prompt: string
}

const root = path.resolve(__dirname, '..')

function readJson<T>(file: string): T {
  return JSON.parse(fs.readFileSync(path.join(root, file), 'utf-8'))
}

export const apps: BenchmarkApp[] = readJson('apps.json')

const deployments: Record<string, string> = readJson('deployments.json')

export function getApp(id: number): BenchmarkApp {
  const app = apps.find((a) => a.id === id)
  if (!app) throw new Error(`Unknown app id ${id}`)
  return app
}

/**
 * Live URL for an app. An environment variable like APP_URL_3 wins over
 * deployments.json, so the builder can pass fresh URLs without editing files.
 */
export function getAppUrl(id: number): string | undefined {
  const url = process.env[`APP_URL_${id}`] || deployments[String(id)]
  return url || undefined
}

/** Tags used for filtering, e.g. --grep @app03 or --grep @level1 */
export function tagsFor(app: BenchmarkApp): string[] {
  return [`@app${String(app.id).padStart(2, '0')}`, `@level${app.level}`]
}

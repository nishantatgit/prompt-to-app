import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,

  // No retries on purpose: a flaky app is not a working app.
  retries: 0,

  reporter: [
    ['list'],
    ['html', { outputFolder: 'results/latest/report', open: 'never' }],
    ['json', { outputFile: 'results/latest/results.json' }],
  ],

  outputDir: 'results/latest/artifacts',

  use: {
    ...devices['Desktop Chrome'],
    screenshot: 'on',
    trace: 'retain-on-failure',
  },
})

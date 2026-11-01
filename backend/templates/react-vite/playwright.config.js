import { defineConfig } from "@playwright/test";

const port = Number(process.env.PORT || 4173);

export default defineConfig({
  testDir: "./tests",
  reporter: [["json", { outputFile: "playwright-results.json" }]],
  // One test fails after 15s instead of the default 30s.
  timeout: 15_000,
  // Playwright stops the whole run at 8 minutes, before the backend's 600s kill,
  // so the JSON report is still written and unfinished tests show as not run.
  globalTimeout: 480_000,
  // An expect on something that never appears fails after 5s.
  expect: { timeout: 5_000 },
  use: {
    baseURL: `http://localhost:${port}`,
    trace: "retain-on-failure",
    // A click or fill on a missing element fails after 5s.
    actionTimeout: 5_000,
  },
  webServer: {
    command: `yarn preview --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});

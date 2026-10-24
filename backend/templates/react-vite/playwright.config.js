import { defineConfig } from "@playwright/test";

const port = Number(process.env.PORT || 4173);

export default defineConfig({
  testDir: "./tests",
  reporter: [["json", { outputFile: "playwright-results.json" }]],
  use: { baseURL: `http://localhost:${port}`, trace: "retain-on-failure" },
  webServer: {
    command: `yarn preview --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});

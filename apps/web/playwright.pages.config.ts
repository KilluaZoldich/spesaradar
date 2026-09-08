import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "../../tests/pages",
  outputDir: "../../.private/pages-test-results",
  workers: 1,
  use: {
    baseURL: process.env.PAGES_TEST_URL || "http://127.0.0.1:8082/spesaradar/",
    viewport: { width: 1280, height: 900 },
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../../docs/pages-e2e-results.json" }],
  ],
});

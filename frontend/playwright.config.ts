import { defineConfig } from "@playwright/test";

/** End-to-end tests against a running LedgerBot (dev.py: API on 8100, app on 5174).
 *  Uses the installed Microsoft Edge so no browser download is needed. Set E2E_BASE_URL to target another host. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5174",
    channel: process.env.E2E_CHANNEL ?? "msedge",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
});

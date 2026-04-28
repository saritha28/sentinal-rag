import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for SentinelRAG frontend e2e specs.
 *
 * The specs target a running Next.js dev server (default) plus the FastAPI
 * backend that next.config.mjs proxies under /api. Both must be reachable
 * locally before specs are useful — see `make up` and `make api`. CI in
 * Phase 7 will run these against a deployed `dev.<domain>`.
 */

const PORT = process.env.E2E_PORT ?? '3000';
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Don't auto-spawn the dev server here — these specs assume `make up` +
  // `make api` + `make frontend` are running. Auto-spawn would couple
  // playwright run-time to a heavy Postgres+Ollama+Keycloak boot.
});

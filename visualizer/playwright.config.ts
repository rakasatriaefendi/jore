import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch:
    process.env.JORE_E2E_MODE === 'development'
      ? '**/mock-state.spec.ts'
      : '**/smoke.spec.ts',
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL:
      process.env.JORE_E2E_MODE === 'development'
        ? 'http://127.0.0.1:5174'
        : 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

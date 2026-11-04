import { defineConfig } from '@playwright/test';

process.loadEnvFile('../backend/.env.integration-test');
process.env.E2E_API_ORIGIN = 'http://127.0.0.1:5001';

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.js',
  globalTeardown: './e2e/global-teardown.js',
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5174',
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'python -m tests.e2e_server',
      cwd: '../backend',
      env: { E2E_BACKEND_PORT: '5001' },
      url: 'http://127.0.0.1:5001/',
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --port 5174 --strictPort',
      env: { E2E_BACKEND_PORT: '5001' },
      url: 'http://localhost:5174',
      reuseExistingServer: false,
    },
  ],
});

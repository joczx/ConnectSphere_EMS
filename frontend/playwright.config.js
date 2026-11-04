import { defineConfig } from '@playwright/test';

// Test account emails and passwords, and the secret key for test data.
process.loadEnvFile('../backend/.env.integration-test');

export default defineConfig({
  testDir: './e2e',
  // Confirmed events and accounts for the registration tests, made and removed once per run.
  globalSetup: './e2e/global-setup.js',
  globalTeardown: './e2e/global-teardown.js',
  workers: 1, // one shared test database
  // Results in the terminal, plus an HTML report for `npx playwright show-report`.
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    // The browser runs in Singapore time, as the users do. Without this it uses the
    // machine's timezone, which is UTC on GitHub's runners, so times typed into the
    // event request form are saved 8 hours off.
    timezoneId: 'Asia/Singapore',
  },
  webServer: [
    { command: 'python -m tests.e2e_server', cwd: '../backend',
      url: 'http://127.0.0.1:5000/', reuseExistingServer: false },
    { command: 'npm run dev', url: 'http://localhost:5173',
      reuseExistingServer: false },
  ],
});

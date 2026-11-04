import { defineConfig } from '@playwright/test';
import base from './playwright.config.js';

// Separate ports leave the developer's normal Flask/Vite session untouched.
process.env.E2E_API_ORIGIN = 'http://127.0.0.1:5001';
const standalone = process.env.E2E_SKIP_REGISTRATION_FIXTURES === '1';
const registrationSpecs = ['attendee-events', 'confirmed-event-info', 'my-registrations', 'register', 'registration-period', 'registration-records', 'withdraw'];
export default defineConfig({
  ...base,
  ...(standalone ? { globalSetup: undefined, globalTeardown: undefined, testIgnore: registrationSpecs.map(name => `**/${name}.spec.js`) } : {}),
  use: { ...base.use, baseURL: 'http://localhost:5174', ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}) },
  webServer: [
    { command: 'python -m tests.e2e_server', cwd: '../backend', env: { E2E_BACKEND_PORT: '5001' }, url: 'http://127.0.0.1:5001/', reuseExistingServer: false },
    { command: 'npm run dev -- --port 5174 --strictPort', env: { E2E_BACKEND_PORT: '5001' }, url: 'http://localhost:5174', reuseExistingServer: false },
  ],
});

// Creates the confirmed events and accounts the registration tests need, by
// running backend/tests/e2e_fixtures.py against the integration-test project.
// That takes the events through the real flow, so it runs once per test run.
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { FIXTURES_FILE } from './helpers.js';

export const STATE_FILE = fileURLToPath(new URL('./.fixtures-state.json', import.meta.url));

export default function globalSetup() {
  const output = execFileSync('python', ['-m', 'tests.e2e_fixtures', 'setup', STATE_FILE], {
    cwd: fileURLToPath(new URL('../../backend', import.meta.url)),
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  writeFileSync(FIXTURES_FILE, output);
}

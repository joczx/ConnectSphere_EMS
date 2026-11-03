// Removes everything global-setup.js created, even when tests failed.
import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { STATE_FILE } from './global-setup.js';
import { FIXTURES_FILE } from './helpers.js';

export default function globalTeardown() {
  execFileSync('python', ['-m', 'tests.e2e_fixtures', 'teardown', STATE_FILE], {
    cwd: fileURLToPath(new URL('../../backend', import.meta.url)),
    stdio: 'inherit',
  });
  rmSync(FIXTURES_FILE, { force: true });
}

// Creates the confirmed events and accounts the registration tests need, by
// running backend/tests/e2e_fixtures.py against the integration-test project.
// That takes the events through the real flow, so it runs once per test run.
import { execFileSync } from 'node:child_process';
import { existsSync, renameSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { FIXTURES_FILE } from './helpers.js';

export const STATE_FILE = fileURLToPath(new URL('./.fixtures-state.json', import.meta.url));
const BACKEND = fileURLToPath(new URL('../../backend', import.meta.url));

// A run stopped before its teardown (Ctrl+C, the UI's Stop button) leaves its
// state file behind. Remove that run's data first: setup would otherwise
// overwrite the file and lose track of it.
function removeStoppedRun() {
  if (!existsSync(STATE_FILE)) return;
  console.log('Removing test data left by a stopped run...');
  try {
    execFileSync('python', ['-m', 'tests.e2e_fixtures', 'teardown', STATE_FILE], { cwd: BACKEND, stdio: 'inherit' });
  } catch {
    // Keep the record rather than overwrite it, so the data can still be removed later with
    // `python -m tests.e2e_fixtures teardown <this file>` from backend/.
    const kept = STATE_FILE.replace(/\.json$/, `.stopped-${Date.now()}.json`);
    renameSync(STATE_FILE, kept);
    console.warn(`Could not remove the stopped run's data; its record is kept in ${kept}.`);
  }
}

export default function globalSetup() {
  removeStoppedRun();
  const output = execFileSync('python', ['-m', 'tests.e2e_fixtures', 'setup', STATE_FILE], {
    cwd: BACKEND,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  writeFileSync(FIXTURES_FILE, output);
}

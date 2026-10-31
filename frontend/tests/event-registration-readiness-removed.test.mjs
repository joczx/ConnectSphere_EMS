import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('event page keeps safety submission and has no registration-readiness control', async () => {
  const source = await readFile(new URL('../src/pages/Events.jsx', import.meta.url), 'utf8');

  assert.match(source, />Submit for safety checks</);
  assert.doesNotMatch(source, /registration_ready/);
  assert.doesNotMatch(source, /registration-readiness/);
  assert.doesNotMatch(source, /Registration arrangements are ready/);
  assert.doesNotMatch(source, /Awaiting coordinator confirmation/);
});

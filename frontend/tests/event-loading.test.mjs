import test from 'node:test';
import assert from 'node:assert/strict';
import { loadEvents } from '../src/services/eventLoading.js';

test('a status service outage still loads visible events with a warning', async () => {
  const calls = [];
  const api = async path => {
    calls.push(path);
    if (path.endsWith('status-refresh')) throw Object.assign(new Error('Not configured.'), { status: 503 });
    return { events: [{ event_id: 1 }] };
  };
  const result = await loadEvents(api, '/api/events');
  assert.deepEqual(calls, ['/api/events/status-refresh', '/api/events']);
  assert.equal(result.data.events.length, 1);
  assert.match(result.statusWarning, /out of date/);
});
test('successful status refresh has no warning', async () => {
  const result = await loadEvents(async () => ({ events: [] }), '/api/events');
  assert.equal(result.statusWarning, '');
});
test('authentication failures and aborted requests do not continue loading', async () => {
  for (const error of [Object.assign(new Error('Sign in.'), { status: 401 }), Object.assign(new Error('Aborted'), { name: 'AbortError' })]) {
    let calls = 0;
    await assert.rejects(loadEvents(async () => { calls++; throw error; }, '/api/events'), error);
    assert.equal(calls, 1);
  }
});
test('event query failures remain errors', async () => {
  const error = Object.assign(new Error('Database unavailable.'), { status: 503 });
  await assert.rejects(loadEvents(async path => {
    if (path === '/api/events') throw error;
    return {};
  }, '/api/events'), error);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { loadEvents, loadEventWorkspace, eventWorkspaceItems } from '../src/services/eventLoading.js';

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

test('workspace combines all own request statuses without duplicating approved events', () => {
  const events = [{ event_id: 1, event_request_id: 10, status: 'confirmed' }];
  const requests = ['draft', 'submitted', 'planning', 'rejected', 'cancelled'].map((status, index) => ({
    event_request_id: index + 20, event_organiser_id: 'me', status,
  }));
  requests.push({ event_request_id: '10', event_organiser_id: 'me', status: 'planning' },
    { event_request_id: 99, event_organiser_id: 'other', status: 'submitted' });
  const result = eventWorkspaceItems(events, requests, 'me');
  assert.equal(result.length, 6);
  assert.deepEqual(result.map(item => item.status), ['confirmed', 'draft', 'submitted', 'planning', 'rejected', 'cancelled']);
  assert.equal(result[1].workspace_path, '/event-requests/20');
  assert.equal(requests[0].workspace_path, undefined);
});

test('workspace requests are organiser-scoped and failures preserve operational events with a warning', async () => {
  const calls = [];
  const result = await loadEventWorkspace(async path => {
    calls.push(path);
    if (path.startsWith('/api/event-requests')) throw new Error('Unavailable');
    return { events: [{ event_id: 1 }] };
  }, '/api/events', {}, 'me');
  assert.ok(calls.includes('/api/event-requests?event_organiser_id=me'));
  assert.equal(result.data.events[0].event_id, 1);
  assert.deepEqual(result.data.event_requests, []);
  assert.match(result.requestWarning, /could not be loaded/);
});

test('other staff do not query organiser requests', async () => {
  const calls = [];
  await loadEventWorkspace(async path => { calls.push(path); return { events: [] }; }, '/api/events');
  assert.deepEqual(calls, ['/api/events/status-refresh', '/api/events']);
});

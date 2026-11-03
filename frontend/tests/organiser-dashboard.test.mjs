import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadOrganiserDashboard } from '../src/services/organiserDashboard.js';

const now = Date.parse('2026-10-31T00:00:00Z');
const own = (event_id, changes = {}) => ({ event_id, event_name: `Event ${event_id}`, event_organiser_id: 'me',
  status: 'confirmed', start_datetime: '2026-11-10T02:00:00Z', registration_opens_at: '2026-11-01T00:00:00Z',
  registration_closes_at: '2026-11-09T00:00:00Z', ...changes });

test('organiser dashboard scopes data, deduplicates requests and aggregates registration totals', async () => {
  const paths = [];
  const responses = {
    '/api/events/status-refresh': {},
    '/api/events': { events: [own(1, { event_request_id: 10 }), own(2, { status: 'pending_safety_checks', registration_opens_at: null }),
      own(3, { status: 'completed', start_datetime: '2026-10-01T00:00:00Z' }), own(4, { status: 'cancelled' }), own(9, { event_organiser_id: 'other', event_coordinator_id: 'me' })] },
    '/api/event-requests?event_organiser_id=me': { event_requests: [
      { event_request_id: 10, event_organiser_id: 'me', status: 'planning' },
      { event_request_id: 20, event_organiser_id: 'me', event_name: 'Draft', status: 'draft' },
      { event_request_id: 21, event_organiser_id: 'me', event_name: 'Rejected', status: 'rejected' },
      { event_request_id: 22, event_organiser_id: 'me', status: 'submitted' },
      { event_request_id: 30, event_organiser_id: 'other', status: 'draft' },
    ] },
    '/api/notifications?limit=5': { items: [{ notification_id: 1, title: 'Event approved', body: 'Ready for planning' }] },
    '/api/events/1/registrations': { total_registered: 2, total_waitlisted: 1, total_withdrawn: 0, registrations: [{ contact_email: 'private@example.com' }] },
    '/api/events/2/registrations': { total_registered: 0, total_waitlisted: 0, total_withdrawn: 0 },
    '/api/venue-bookings/events/1': { bookings: [{ status: 'approved', venue_name: 'Approved Hall' }, { status: 'submitted', venue_name: 'Unapproved Hall' }] },
    '/api/venue-bookings/events/2': { bookings: [] },
  };
  const result = await loadOrganiserDashboard(async path => {
    paths.push(path); assert.ok(path in responses, path); return responses[path];
  }, 'me', undefined, now);
  assert.deepEqual(result.counts, { confirmed: 1, pending_safety_checks: 1, completed: 1, cancelled: 1, draft: 1, rejected: 1, submitted: 1 });
  assert.deepEqual(result.attention.map(item => item.action), ['Finish draft request', 'Amend rejected request', 'Set registration dates']);
  assert.deepEqual(result.registrationSummary, { confirmed: 2, waitlisted: 1, withdrawn: 0 });
  assert.deepEqual(result.upcoming.map(item => item.event_id), [1, 2]);
  assert.deepEqual(result.upcoming[0].venues, ['Approved Hall']);
  assert.ok(!JSON.stringify(result).includes('private@example.com'), 'dashboard retains counts, not attendee contact details');
  assert.ok(!paths.some(path => path.includes('/9/')));
  assert.equal(result.updates[0].title, 'Event approved');
});

test('empty dashboard returns zero counts with no roster or venue lookups', async () => {
  const paths = [];
  const result = await loadOrganiserDashboard(async path => {
    paths.push(path); return { events: [], event_requests: [], items: [] };
  }, 'me', undefined, now);
  assert.deepEqual(result.counts, {});
  assert.deepEqual(result.registrationSummary, { confirmed: 0, waitlisted: 0, withdrawn: 0 });
  assert.deepEqual(result.attention, []);
  assert.equal(paths.length, 4);
});

test('failed queries and roster reads are unavailable rather than misleading zero totals', async () => {
  const result = await loadOrganiserDashboard(async path => {
    if (path === '/api/events/status-refresh') return {};
    if (path === '/api/events') return { events: [own(1)] };
    if (path.startsWith('/api/venue-bookings')) return { bookings: [] };
    throw new Error('Unavailable');
  }, 'me', undefined, now);
  assert.equal(result.counts, null);
  assert.equal(result.registrationSummary, null);
  assert.equal(result.upcoming[0].registrations, null);
  assert.equal(result.updates, null);
  assert.equal(result.warnings.length, 3);
});

test('missing identity prevents all dashboard queries', async () => {
  let calls = 0;
  await assert.rejects(loadOrganiserDashboard(async () => { calls++; }, null), /identify your account/);
  assert.equal(calls, 0);
});

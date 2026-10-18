import { test } from 'node:test';
import assert from 'node:assert/strict';
import { countStatuses, loadDashboard, upcomingEvents } from '../src/services/dashboard.js';

function mockApi(responses) {
  const paths = [];
  const api = async path => {
    if (path === '/api/events/status-refresh') return {};
    paths.push(path);
    if (!(path in responses)) throw new Error('Unexpected endpoint: ' + path);
    const response = responses[path];
    if (response instanceof Error) throw response;
    return response;
  };
  return { api, paths };
}
test('organiser dashboard uses only their requests and preserves distinct status counts', async () => {
  const { api, paths } = mockApi({
    '/api/events': { events: [] },
    '/api/event-requests?event_organiser_id=me': { event_requests: [{ status: 'draft' }, { status: 'submitted' }, { status: 'planning' }, { status: 'rejected' }] },
  });
  const data = await loadDashboard(api, ['Event Organiser'], 'me');
  assert.equal(paths.length, 2);
  assert.equal(data.sections[0].reviewed, 2);
  assert.deepEqual(data.sections[0].counts, { draft: 1, submitted: 1, planning: 1, rejected: 1 });
});
test('coordinator sees assigned requests and equipment for assigned events only', async () => {
  const { api, paths } = mockApi({
    '/api/events': { events: [{ event_id: 1, event_coordinator_id: 'me', status: 'planning' }, { event_id: 2, event_coordinator_id: 'other', status: 'planning' }] },
    '/api/event-requests': { event_requests: [{ event_coordinator_id: 'me', status: 'submitted' }, { event_coordinator_id: 'other', status: 'submitted' }] },
    '/api/venue-bookings': { bookings: [{ status: 'approved' }] },
    '/api/events/1/equipment-requests': { equipment_requests: [{ status: 'partially_accepted' }] },
  });
  const data = await loadDashboard(api, ['event_coordinator'], 'me');
  assert.equal(data.sections.find(s => s.id === 'review-requests').total, 1);
  assert.equal(data.sections.find(s => s.id === 'equipment').counts.partially_accepted, 1);
  assert.equal(paths.includes('/api/events/2/equipment-requests'), false);
});
test('technical and venue staff receive review queues without organiser or coordinator requests', async () => {
  const { api, paths } = mockApi({
    '/api/events': { events: [] },
    '/api/venue-bookings': { bookings: [{ status: 'submitted' }] },
    '/api/equipment-request-reviews': { equipment_requests: [{ status: 'pending' }, { status: 'accepted' }] },
  });
  const data = await loadDashboard(api, ['Technical Support Staff', 'Venue Staff'], 'me');
  assert.equal(data.sections.find(s => s.id === 'equipment').reviewed, 1);
  assert.equal(paths.some(path => path.startsWith('/api/event-requests')), false);
});
test('lead gets unassigned count and a failed section is unavailable instead of zero', async () => {
  const { api } = mockApi({ '/api/events': new Error('Unavailable'), '/api/event-requests/unassigned': { event_requests: [{ event_request_id: 4 }] } });
  const data = await loadDashboard(api, ['Event Coordinator Lead'], 'me');
  assert.equal(data.sections[0].counts.submitted, 1);
  assert.equal(data.sections.some(s => s.id === 'events'), false);
  assert.equal(data.warnings.length, 1);
});
test('upcoming events exclude terminal and ended events and sort by start', () => {
  const events = [
    { event_id: 1, status: 'cancelled', start_datetime: '2030-02-01' },
    { event_id: 2, status: 'confirmed', start_datetime: '2030-02-03' },
    { event_id: 3, status: 'planning', start_datetime: '2030-02-02' },
    { event_id: 4, status: 'completed', start_datetime: '2030-02-01' },
    { event_id: 5, status: 'confirmed', start_datetime: '2029-01-01' },
  ];
  assert.deepEqual(upcomingEvents(events, Date.parse('2030-01-01')).map(e => e.event_id), [3, 2]);
  assert.deepEqual(countStatuses([]), {});
});

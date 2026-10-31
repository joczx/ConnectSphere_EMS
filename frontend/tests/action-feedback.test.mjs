import { test } from 'node:test';
import assert from 'node:assert/strict';
import { actionMessage, shouldNotify } from '../src/services/actionFeedback.js';

test('user writes receive feedback while background reads and status refreshes stay quiet', () => {
  for (const method of ['POST', 'PATCH', 'PUT', 'DELETE']) assert.equal(shouldNotify('/api/events/1', { method }), true);
  assert.equal(shouldNotify('/api/events', {}), false);
  assert.equal(shouldNotify('/api/events/status-refresh', { method: 'POST' }), false);
  assert.equal(shouldNotify('/api/venues/search?name=Hall', { feedback: true }), true);
  assert.equal(shouldNotify('/api/event-requests/1', { method: 'PATCH', feedback: false }), false);
  assert.equal(shouldNotify('/api/event-requests/1', { method: 'PATCH', successFeedback: false }), true, 'intermediate saves must still show errors');
});

test('fallback messages distinguish reservation, cancellation and review actions', () => {
  assert.equal(actionMessage('/api/equipment/reservations', 'POST', {}), 'Equipment reserved successfully.');
  assert.equal(actionMessage('/api/equipment/reservations/1', 'DELETE', {}), 'Equipment reservation cancelled.');
  assert.equal(actionMessage('/api/events/1/cancel', 'POST', {}), 'Cancellation recorded successfully.');
  assert.equal(actionMessage('/api/venue-bookings/1/review', 'POST', {}), 'Review decision recorded successfully.');
  assert.equal(actionMessage('/api/event-requests', 'POST', { message: 'Draft event request saved.' }), 'Draft event request saved.');
});

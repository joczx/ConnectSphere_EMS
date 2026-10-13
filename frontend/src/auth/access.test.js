import test from 'node:test';
import assert from 'node:assert/strict';
import { hasAccess, rolesForPath } from './access.js';

const allowed = (path, roles) => hasAccess(roles, rolesForPath(path));
test('role-specific pages reject other roles including nested URLs', () => {
  assert.equal(allowed('/equipment', ['Event Organiser']), false);
  assert.equal(allowed('/equipment', ['technical_support_staff']), true);
  assert.equal(allowed('/review-event-requests/123', ['Event Organiser']), false);
  assert.equal(allowed('/review-event-requests/123', ['Event Coordinator']), true);
  assert.equal(allowed('/review-venue-bookings/123', ['Venue Staff']), true);
  assert.equal(allowed('/review-venue-bookings/123', ['Event Coordinator']), false);
});
test('venue browsing is shared but editing requires venue staff', () => {
  assert.equal(allowed('/venues/123', ['Event Coordinator']), true);
  for (const path of ['/venues/new', '/venues/123/edit', '/venues/123/delete']) {
    assert.equal(allowed(path, ['Event Coordinator']), false);
    assert.equal(allowed(path, ['Venue Staff']), true);
  }
});
test('multiple roles combine access and unknown roles cannot access restricted pages', () => {
  assert.equal(allowed('/equipment', ['Venue Staff', 'Technical Support']), true);
  assert.equal(allowed('/event-requests/new', ['event_organizer']), true);
  assert.equal(allowed('/equipment', []), false);
  assert.equal(allowed('/equipment', ['Unknown']), false);
});

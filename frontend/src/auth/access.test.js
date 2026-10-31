import test from 'node:test';
import assert from 'node:assert/strict';
import { can, canViewEvent, hasAccess, rolesForPath } from './access.js';

const allowed = (path, roles) => hasAccess(roles, rolesForPath(path));

test('only attendees can browse registration events, including direct URLs', () => {
  assert.equal(allowed('/event-registration', ['Attendee']), true);
  assert.equal(allowed('/event-registration/7', ['attendee']), true);
  assert.equal(allowed('/my-registrations', ['Attendee']), true);
  for (const roles of [[], ['Event Organiser'], ['Event Coordinator'], ['Safety Officer'], ['Venue Staff'], ['Technical Support Staff'], ['Event Coordinator Lead']]) {
    assert.equal(allowed('/event-registration', roles), false);
    assert.equal(allowed('/my-registrations', roles), false);
  }
});
test('role-specific pages reject other roles including nested URLs', () => {
  assert.equal(allowed('/equipment', ['Event Organiser']), false);
  assert.equal(allowed('/equipment', ['technical_support_staff']), true);
  assert.equal(allowed('/review-event-requests/123', ['Event Organiser']), false);
  assert.equal(allowed('/review-event-requests/123', ['Event Coordinator']), true);
  assert.equal(allowed('/review-venue-bookings/123', ['Venue Staff']), true);
  assert.equal(allowed('/review-venue-bookings/123', ['Event Coordinator']), false);
  assert.equal(allowed('/operational-safety-reviews', ['Safety Officer']), true);
  assert.equal(allowed('/operational-safety-reviews', ['Event Coordinator']), false);
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

test('requesting equipment is for coordinators, reviewing it for technical support', () => {
  assert.equal(allowed('/equipment-requests', ['Event Coordinator']), true);
  assert.equal(allowed('/equipment-requests', ['Technical Support Staff']), false);
  assert.equal(allowed('/equipment-requests', ['Event Organiser']), false);
  assert.equal(allowed('/equipment', ['Event Coordinator']), false);
});

test('venues are for coordinators and venue staff; event management is for staff', () => {
  for (const path of ['/venues', '/venues/123']) {
    assert.equal(allowed(path, ['Event Coordinator']), true);
    assert.equal(allowed(path, ['Venue Staff']), true);
    for (const role of ['Event Organiser', 'Technical Support Staff', 'Safety Officer', 'Event Coordinator Lead']) {
      assert.equal(allowed(path, [role]), false, `${role} on ${path}`);
    }
  }
  for (const role of ['Event Organiser', 'Event Coordinator', 'Event Coordinator Lead', 'Venue Staff', 'Technical Support Staff', 'Safety Officer']) {
    assert.equal(allowed('/events/7', [role]), true);
    assert.equal(allowed('/home', [role]), true);
  }
  for (const path of ['/events', '/events/7']) {
    for (const roles of [[], ['Attendee'], ['Unknown']]) {
      assert.equal(allowed(path, roles), false);
    }
  }
  assert.equal(allowed('/event-registration', ['Attendee']), true);
  assert.equal(allowed('/my-registrations', ['Attendee']), true);
  assert.equal(allowed('/home', ['Attendee']), true);
});

test('a lead is not a coordinator and a coordinator is not a lead', () => {
  assert.equal(allowed('/review-event-requests', ['Event Coordinator Lead']), false);
  assert.equal(allowed('/venue-bookings', ['Event Coordinator Lead']), false);
  assert.equal(allowed('/assign-event-coordinators', ['Event Coordinator']), false);
});

const event = {
  event_organiser_id: 'org', event_coordinator_id: 'coord',
  technical_support_id: 'tech', venue_staff_id: 'vs', safety_officer_id: 'safety',
};

test('only the assigned coordinator edits, cancels and requests for an event', () => {
  for (const action of ['event.edit', 'event.cancel', 'event.registrationReady', 'event.findVenue', 'equipment.request']) {
    assert.equal(can(['Event Coordinator'], 'coord', action, event), true, action);
    assert.equal(can(['Event Coordinator'], 'someone-else', action, event), false, action);
    // Linked to the event, but in another role.
    assert.equal(can(['Event Organiser'], 'org', action, event), false, action);
    assert.equal(can(['Venue Staff'], 'vs', action, event), false, action);
    assert.equal(can(['Technical Support Staff'], 'tech', action, event), false, action);
  }
});

test('organiser and technical support actions need both the role and the link', () => {
  assert.equal(can(['Event Organiser'], 'org', 'changeRequest.create', event), true);
  assert.equal(can(['Event Organiser'], 'coord', 'changeRequest.create', event), false);
  assert.equal(can(['Technical Support Staff'], 'tech', 'equipment.review', event), true);
  assert.equal(can(['Technical Support Staff'], 'other', 'equipment.review', event), false);
  assert.equal(can(['Event Organiser'], 'org', 'event.create'), true);
  assert.equal(can(['Event Coordinator'], 'coord', 'event.create'), false);
});

test('only the assigned safety officer decides the safety review of an event', () => {
  assert.equal(can(['Safety Officer'], 'safety', 'safety.decide', event), true);
  assert.equal(can(['Safety Officer'], 'another-officer', 'safety.decide', event), false);
  assert.equal(can(['Event Coordinator'], 'safety', 'safety.decide', event), false);
});

test('without a record only the role is checked; unknown actions are refused', () => {
  assert.equal(can(['Venue Staff'], 'vs', 'booking.review'), true);
  assert.equal(can(['Event Coordinator'], 'coord', 'booking.review'), false);
  assert.equal(can(['Venue Staff'], 'vs', 'venue.create'), true);
  assert.equal(can(['Event Coordinator'], 'coord', 'venue.viewCalendar'), true);
  assert.equal(can(['Event Organiser'], 'org', 'venue.viewCalendar'), false);
  assert.equal(can(['Venue Staff'], 'vs', 'no.such.action'), false);
  assert.equal(can([], null, 'event.edit', event), false);
  assert.equal(can(['Event Coordinator'], null, 'event.edit', event), false);
});

test('users see only events they are assigned to; a lead sees every event', () => {
  for (const [role, id] of [['Event Organiser', 'org'], ['Event Coordinator', 'coord'], ['Technical Support Staff', 'tech'], ['Venue Staff', 'vs']]) {
    assert.equal(canViewEvent([role], id, event), true, role);
    assert.equal(canViewEvent([role], 'someone-else', event), false, role);
  }
  assert.equal(canViewEvent(['Safety Officer'], 'safety', event), true);
  assert.equal(canViewEvent(['Safety Officer'], 'another-officer', event), false);
  assert.equal(canViewEvent(['Event Coordinator Lead'], 'lead', event), true);
  assert.equal(canViewEvent(['Event Coordinator'], null, event), false);
  assert.equal(canViewEvent(['Event Coordinator Lead'], 'lead', null), false);
});

test('coordinator assignment and reassignment are restricted to leads', () => {
  for (const path of ['/assign-event-coordinators', '/reassign-event-coordinators']) {
    assert.equal(allowed(path, ['Event Coordinator']), false);
    assert.equal(allowed(path, ['Event Coordinator Lead']), true);
    assert.equal(allowed(path, []), false);
  }
});

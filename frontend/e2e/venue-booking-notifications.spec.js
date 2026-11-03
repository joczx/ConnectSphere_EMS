// SCRUM-264 Notification for Venue Booking Request and Reservation
//   AC1  The Event Coordinator is sent a confirmation when a venue booking request
//        is successfully submitted.
//   AC2  The Venue Staff assigned to the event are notified of a new booking request.
//   AC3  The Event Coordinator is notified when the booking request is approved or rejected.
//   AC4  Each notification includes the booking details: event name, venue and status.
//
// The Coordinator submits and Venue Staff decide through the app's pages; the
// event in planning and the venues are arranged before the tests. Every
// notification is checked on the recipient's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { account, admin, apiAs, signIn, userId } from './helpers.js';

// Each step continues the bookings the one before made.
test.describe.configure({ mode: 'serial' });

const name = `E2E venue booking ${Date.now()}`;
const starts = DateTime.now().setZone('Asia/Singapore').plus({ days: 100 })
  .set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const ends = starts.plus({ hours: 3 });
let event, approvedVenue, rejectedVenue, approvedBooking, rejectedBooking;

const newVenue = label => admin('/rest/v1/venues', { method: 'POST', body: {
  venue_name: `E2E ${label} ${Date.now()}`, capacity: 100, postal_code: '123456', block_number: '1',
  street_name: 'E2E Street', wheelchair_accessible: false, blind_accessible: false,
  facilities: ['projector'], supported_room_layouts: ['theatre'],
  operating_hours: Object.fromEntries(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    .map(day => [day, { open: '08:00', close: '22:00' }])),
  default_setup_minutes: 0, default_turnaround_minutes: 0,
} }).then(rows => rows[0]);

test.beforeAll(async ({ request }) => {
  const { event_request: submitted } = await apiAs(request, 'Event Organiser', 'POST', '/api/event-requests', {
    event_name: name, purpose: 'E2E test', description: 'Created by venue-booking-notifications.spec.js.',
    event_organiser_id: await userId('Event Organiser'),
    start_datetime: starts.toISO(), end_datetime: ends.toISO(), capacity_needed: 40,
    room_layout: 'theatre', required_facilities: ['projector'], equipment_requirements: [],
  });
  await apiAs(request, 'Event Coordinator Lead', 'POST', `/api/event-requests/${submitted.event_request_id}/assign-coordinator`,
    { coordinator_id: await userId('Event Coordinator') });
  await apiAs(request, 'Event Coordinator', 'POST', `/api/event-requests/${submitted.event_request_id}/review`,
    { outcome: 'approved' });
  [event] = await admin(`/rest/v1/events?select=*&event_request_id=eq.${submitted.event_request_id}`);
  // AC2 is about the event's assigned Venue Staff, so it must be the test account.
  expect(event.venue_staff_id, 'approval assigned another Venue Staff user').toBe(await userId('Venue Staff'));
  approvedVenue = await newVenue('Hall');
  rejectedVenue = await newVenue('Annex');
});

test.afterAll(async () => {
  for (const venue of [approvedVenue, rejectedVenue].filter(Boolean)) {
    for (const table of ['venue_booking_requests', 'venue_blocks', 'venues']) {
      await admin(`/rest/v1/${table}?venue_id=eq.${venue.venue_id}`, { method: 'DELETE' });
    }
  }
  if (event) {
    await admin(`/rest/v1/events?event_id=eq.${event.event_id}`, { method: 'DELETE' });
    await admin(`/rest/v1/event_request?event_request_id=eq.${event.event_request_id}`, { method: 'DELETE' });
  }
  await admin(`/rest/v1/notifications?body=like.*${encodeURIComponent('E2E venue booking')}*`, { method: 'DELETE' });
});

async function notification(page, title, venue) {
  await page.goto('/#/notifications');
  const item = page.getByRole('main').getByRole('listitem')
    .filter({ hasText: title }).filter({ hasText: name }).filter({ hasText: venue.venue_name });
  await expect(item).toHaveCount(1);
  return item;
}

async function review(page, booking, outcome, comments) {
  await signIn(page, 'Venue Staff');
  await page.goto(`/#/review-venue-bookings/${booking}`);
  if (comments) await page.getByLabel(/Comments for the Event Coordinator/).fill(comments);
  const verb = outcome === 'approved' ? 'Approve' : 'Reject';
  await page.getByRole('button', { name: verb, exact: true }).click();
  // The page asks for confirmation, since a decision cannot be changed.
  await page.getByRole('button', { name: `${verb} booking` }).click();
  await expect(page.getByRole('button', { name: verb, exact: true })).toHaveCount(0);
}

const venueStaffName = async () =>
  (await admin(`/rest/v1/users?select=name&email=eq.${encodeURIComponent(account('Venue Staff').email)}`))[0].name;

// E2E-NVB-001 (AC1, AC4): the Coordinator submits a booking request and is sent a
// confirmation naming the venue, the event and its pending status.
test('confirms a submitted booking request to the Coordinator', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/venue-bookings?event_id=${event.event_id}&venue_id=${approvedVenue.venue_id}`);
  await page.getByLabel('Venue requirements').fill('E2E test: theatre layout with a projector.');
  await page.getByRole('button', { name: 'Submit booking request' }).click();
  // Scoped to the page body: a pop-up toast repeats the confirmation.
  const confirmation = page.getByRole('main').getByRole('status').filter({ hasText: 'Booking request submitted' });
  await expect(confirmation).toContainText(approvedVenue.venue_name);
  approvedBooking = (await confirmation.getByText(/^Reference:/).textContent()).replace('Reference:', '').trim();

  const item = await notification(page, 'Venue booking request submitted', approvedVenue);
  await expect(item).toContainText(`Your venue booking request for ${approvedVenue.venue_name} for ${name}`);
  await expect(item).toContainText('Status: pending Venue Staff review.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/venue-bookings/${approvedBooking}$`));
});

// E2E-NVB-002 (AC2, AC4): the event's Venue Staff are told of the new request,
// with the venue, event and status, and the notification opens it for review.
test('notifies the assigned Venue Staff of the new request', async ({ page }) => {
  await signIn(page, 'Venue Staff');

  const item = await notification(page, 'New venue booking request', approvedVenue);
  await expect(item).toContainText(`requested ${approvedVenue.venue_name} for ${name}`);
  await expect(item).toContainText('Status: pending review.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/review-venue-bookings/${approvedBooking}$`));
});

// E2E-NVB-003 (AC3, AC4): Venue Staff reject a second request with a reason; the
// Coordinator is told it was rejected, by whom and why.
test('notifies the Coordinator that a request was rejected', async ({ page, request }) => {
  ({ booking: { booking_id: rejectedBooking } } = await apiAs(request, 'Event Coordinator', 'POST', '/api/venue-bookings', {
    event_id: event.event_id, venue_id: rejectedVenue.venue_id, event_name: name, attendance: 40,
    venue_requirements: 'E2E test', starts_at: event.start_datetime, ends_at: event.end_datetime,
  }));
  await review(page, rejectedBooking, 'rejected', 'The annex is being renovated.');

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Venue booking rejected', rejectedVenue);
  await expect(item).toContainText(`has been rejected by ${await venueStaffName()}.`);
  await expect(item).toContainText('Reason: The annex is being renovated.');
});

// E2E-NVB-004 (AC3, AC4): Venue Staff approve the first request; the Coordinator
// is told it was approved, by whom, and the notification opens the booking.
test('notifies the Coordinator that a request was approved', async ({ page }) => {
  await review(page, approvedBooking, 'approved');

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Venue booking approved', approvedVenue);
  await expect(item).toContainText(`Your venue booking request for ${approvedVenue.venue_name} for ${name}`);
  await expect(item).toContainText(`has been approved by ${await venueStaffName()}.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/venue-bookings/${approvedBooking}$`));
});

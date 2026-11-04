// SCRUM-269 Notification for Venue Unavailability
//   AC1  The Event Coordinator is notified when a venue booked for their event
//        becomes unavailable.
//   AC2  The notification identifies the affected venue and event.
//   AC3  The Event Coordinator is notified if the unavailability affects a pending
//        booking request.
//
// Two events are booked at one venue, one approved and one still pending. Venue
// Staff then mark the venue unavailable over both on its venue page. Every
// notification is checked on the Coordinator's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  apiAs, approvedEvent, bookVenue, inputTime, newVenue, notification, notifiedTime, removeRequests,
  removeVenues, signIn,
} from './helpers.js';

// Both tests read the notifications the one unavailable period caused.
test.describe.configure({ mode: 'serial' });

const name = `E2E venue unavailable ${Date.now()}`;
const starts = DateTime.now().plus({ days: 150 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const reason = 'Flooding';
let venue, approvedFor, pendingFor, approvedBooking, pendingBooking, from, until;

test.beforeAll(async ({ request }) => {
  approvedFor = await approvedEvent(request, `${name} approved`, starts);
  pendingFor = await approvedEvent(request, `${name} pending`, starts.plus({ days: 1 }));
  venue = await newVenue('Flood Hall');
  approvedBooking = await bookVenue(request, approvedFor, venue);
  pendingBooking = await bookVenue(request, pendingFor, venue);
  await apiAs(request, 'Venue Staff', 'POST', `/api/venue-bookings/${approvedBooking.booking_id}/review`,
    { outcome: 'approved' });
});

test.afterAll(async () => {
  await removeVenues([venue]);
  await removeRequests([approvedFor, pendingFor].filter(Boolean).map(e => e.event_request_id), name);
});

const affects = (kind, event) => `${venue.venue_name} is unavailable from ${notifiedTime(from)} to `
  + `${notifiedTime(until)} SGT (${reason}), which affects your ${kind} ${venue.venue_name} for ${event.event_name} `
  + `(${notifiedTime(event.start_datetime)} – ${notifiedTime(event.end_datetime)} SGT). It has been cancelled.`;

// E2E-NVU-001 (AC1, AC2): Venue Staff mark the venue unavailable over the event's
// approved booking; the Coordinator is told which venue, when, why and which
// event is affected, and the notification opens the booking.
test('notifies the Coordinator that a booked venue became unavailable', async ({ page }) => {
  from = starts.minus({ days: 1 });
  until = starts.plus({ days: 2 });
  await signIn(page, 'Venue Staff');
  await page.goto(`/#/venues/${venue.venue_id}`);
  const form = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Mark temporarily unavailable' }) });
  await form.getByLabel('Start').fill(inputTime(from));
  await form.getByLabel('End').fill(inputTime(until));
  await form.getByLabel('Reason').fill(reason);
  // The page asks the browser to confirm, since affected bookings are cancelled.
  page.once('dialog', dialog => dialog.accept());
  await form.getByRole('button', { name: 'Mark unavailable' }).click();
  await expect(form.getByRole('status')).toContainText('These bookings were cancelled:');

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Venue unavailable', approvedFor.event_name);
  await expect(item).toContainText(affects('approved booking of', approvedFor));
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/venue-bookings/${approvedBooking.booking_id}$`));
});

// E2E-NVU-002 (AC2, AC3): the same unavailable period covers a booking request still
// pending review; the Coordinator is told that pending request was affected.
test('notifies the Coordinator that a pending request was affected', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Venue unavailable', pendingFor.event_name);
  await expect(item).toContainText(affects('pending booking request for', pendingFor));
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/venue-bookings/${pendingBooking.booking_id}$`));
});

// SCRUM-268 Notification for Tentative Holds
//   AC1  The Event Coordinator is notified when Venue Staff place a tentative hold on
//        a venue for their event.
//   AC2  The notification includes the venue, event name, and hold expiry date and time.
//   AC3  A reminder is sent before the hold expires, and a separate notification
//        when the hold has expired.
//
// Venue Staff place the hold on the booking's review page. The reminder and the
// expiry come from expire_venue_holds(), which pg_cron runs every minute; the
// tests move the hold's expiry as if time had passed and run it themselves.
// Every notification is checked on the Coordinator's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  admin, approvedEvent, bookVenue, inputTime, newVenue, notification, notifiedTime, removeRequests,
  removeVenues, signIn,
} from './helpers.js';

// Each step continues the hold the one before placed.
test.describe.configure({ mode: 'serial' });

const name = `E2E tentative hold ${Date.now()}`;
const starts = DateTime.now().plus({ days: 140 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
let event, venue, booking;

test.beforeAll(async ({ request }) => {
  event = await approvedEvent(request, name, starts);
  venue = await newVenue('Hold Hall');
  booking = await bookVenue(request, event, venue);
});

test.afterAll(async () => {
  await removeVenues([venue]);
  if (event) await removeRequests([event.event_request_id], name);
});

// "<venue> for <event> (<start> – <end> SGT)", as hold notifications describe the booking.
const bookingText = () => `${venue.venue_name} for ${name} (${notifiedTime(event.start_datetime)} – `
  + `${notifiedTime(event.end_datetime)} SGT)`;

// Arrange: the hold now expires at `expires`, as if time had passed, then run the job.
async function passTimeTo(expires) {
  await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`,
    { method: 'PATCH', body: { hold_expires_at: expires.toUTC().toISO() } });
  await admin('/rest/v1/rpc/expire_venue_holds', { method: 'POST', body: {} });
}

// E2E-NTH-001 (AC1, AC2): Venue Staff hold the venue for 30 hours; the Coordinator is
// told the venue, the event and when the hold expires, and it opens the booking.
test('notifies the Coordinator that a tentative hold was placed', async ({ page }) => {
  const expires = DateTime.now().plus({ hours: 30 }).startOf('minute');
  await signIn(page, 'Venue Staff');
  await page.goto(`/#/review-venue-bookings/${booking.booking_id}`);
  await page.getByLabel('Hold expires').fill(inputTime(expires));
  await page.getByRole('button', { name: 'Place tentative hold' }).click();
  await expect(page.getByRole('button', { name: 'Release hold' })).toBeVisible();

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Tentative hold placed', name);
  await expect(item).toContainText(
    `Venue Staff have placed a tentative hold on ${bookingText()}. It expires on ${notifiedTime(expires)} SGT.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/venue-bookings/${booking.booking_id}$`));
});

// E2E-NTH-002 (AC3): with 2 hours left on the hold, the Coordinator is reminded of
// the venue, event and expiry.
test('reminds the Coordinator before the hold expires', async ({ page }) => {
  const expires = DateTime.now().plus({ hours: 2 }).startOf('minute');
  await passTimeTo(expires);

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Tentative hold expiring soon', name);
  await expect(item).toContainText(`Reminder: the tentative hold on ${venue.venue_name} for ${name} expires on `
    + `${notifiedTime(expires)} SGT. Unless Venue Staff confirm the booking by then, the venue becomes available to other requests.`);
});

// E2E-NTH-003 (AC3): once the hold has expired, the Coordinator gets a separate
// notification that the venue is available to others; the reminder is still there.
test('notifies the Coordinator separately when the hold has expired', async ({ page }) => {
  const expired = DateTime.now().minus({ minutes: 1 }).startOf('minute');
  await passTimeTo(expired);

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Tentative hold expired', name);
  await expect(item).toContainText(`The tentative hold on ${bookingText()} expired on ${notifiedTime(expired)} SGT. `
    + 'The venue is now available to other requests.');
  await expect(page.getByRole('main').getByRole('listitem')
    .filter({ hasText: 'Tentative hold expiring soon' }).filter({ hasText: name })).toHaveCount(1);
});

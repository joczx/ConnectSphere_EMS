// SCRUM-270 Notification for Safety Officer Checking
//   AC1  The Safety Officer is notified when an event is submitted for safety review.
//   AC2  The notification shows the event name, event date, and a link to the event.
//
// The Coordinator submits the event on its event page. The event in planning and
// the approved venue booking safety submission needs are arranged before the
// test. The notification is checked on the Safety Officer's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  apiAs, approvedEvent, bookVenue, nameOf, newVenue, notification, notifiedTime, removeRequests,
  removeVenues, signIn, userId,
} from './helpers.js';

const name = `E2E safety check ${Date.now()}`;
const starts = DateTime.now().plus({ days: 160 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
let event, venue;

test.beforeAll(async ({ request }) => {
  event = await approvedEvent(request, name, starts);
  // AC1 is checked as the event's Safety Officer, so it must be the test account.
  expect(event.safety_officer_id, 'approval assigned another Safety Officer').toBe(await userId('Safety Officer'));
  venue = await newVenue('Safety Hall');
  const booking = await bookVenue(request, event, venue);
  await apiAs(request, 'Venue Staff', 'POST', `/api/venue-bookings/${booking.booking_id}/review`, { outcome: 'approved' });
});

test.afterAll(async () => {
  await removeVenues([venue]);
  if (event) await removeRequests([event.event_request_id], name);
});

// E2E-NSO-001 (AC1, AC2): the Coordinator submits the event for safety checks; the
// Safety Officer is told the event name, its date and times, and who submitted it,
// and the notification opens the event's safety review.
test('notifies the Safety Officer of an event submitted for safety review', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/events/${event.event_id}`);
  await page.getByRole('button', { name: 'Submit for safety checks' }).click();
  // The page asks for confirmation, since the event cannot be edited during review.
  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  await expect(page.locator('#event-safety-submission').getByRole('status')).toBeVisible();

  await signIn(page, 'Safety Officer');
  const item = await notification(page, 'Event awaiting safety check', name);
  await expect(item).toContainText(`${name} (${notifiedTime(event.start_datetime)} – `
    + `${notifiedTime(event.end_datetime)} SGT) has been submitted for safety checks by ${await nameOf('Event Coordinator')}.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/operational-safety-reviews/${event.event_id}$`));
  await expect(page.getByRole('main').getByText(name).first()).toBeVisible();
});

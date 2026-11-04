import { test, expect, admin, signIn, inputTime, waitForSave } from './story-fixtures.js';
import { DateTime } from 'luxon';

// SCRUM-220: browser creates a timed hold; real expiry job releases it.
test('SCRUM-220: a timed tentative hold expires without becoming an approval', async ({ page, story }) => {
  const event = await story.event(); const venue = await story.venue(); const booking = await story.book(event, venue);
  await signIn(page, 'Venue Staff'); await page.goto(`/#/review-venue-bookings/${booking.booking_id}`);
  await page.getByLabel('Hold expires').fill(inputTime(DateTime.now().plus({ days: 1 })));
  await waitForSave(page, `/api/venue-bookings/${booking.booking_id}/hold`, () => page.getByRole('button', { name: 'Place tentative hold' }).click());
  const [held] = await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`);
  expect(held.hold_expires_at).toBeTruthy();
  // Arrange elapsed time; do not wait a day or replace the expiry function.
  await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`, { method: 'PATCH', body: { hold_expires_at: DateTime.now().minus({ minutes: 1 }).toISO() } });
  await admin('/rest/v1/rpc/expire_venue_holds', { method: 'POST', body: {} });
  await page.reload(); await expect(page.getByRole('main')).toContainText(/expired/i);
  expect((await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`))[0].status).not.toBe('approved');
});

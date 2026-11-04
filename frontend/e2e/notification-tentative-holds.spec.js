import { test, expect, admin, notifications } from './story-fixtures.js';
import { DateTime } from 'luxon';

// SCRUM-268 AC1-3: notification of hold, reminder and expiry via real scheduled function.
test('SCRUM-268: coordinator receives hold placement, reminder and expiry notices', async ({ page, story }) => {
  const event = await story.event(); const venue = await story.venue(); const booking = await story.book(event, venue);
  await story.call('Venue Staff', 'POST', `/api/venue-bookings/${booking.booking_id}/hold`, { expires_at: DateTime.now().plus({ days: 1 }).toISO() });
  const hold = await notifications(page, 'Event Coordinator', event.event_name, 'Tentative hold placed');
  await expect(hold).toContainText(venue.venue_name);
  await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`, { method: 'PATCH', body: { hold_expires_at: DateTime.now().plus({ minutes: 10 }).toISO() } });
  await admin('/rest/v1/rpc/expire_venue_holds', { method: 'POST', body: {} });
  await notifications(page, 'Event Coordinator', event.event_name, 'Tentative hold expiring soon');
  await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`, { method: 'PATCH', body: { hold_expires_at: DateTime.now().minus({ minutes: 1 }).toISO() } });
  await admin('/rest/v1/rpc/expire_venue_holds', { method: 'POST', body: {} });
  await notifications(page, 'Event Coordinator', event.event_name, 'Tentative hold expired');
});

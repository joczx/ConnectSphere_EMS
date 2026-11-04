import { test, expect, signIn, notifications } from './story-fixtures.js';

// SCRUM-227: real venue block identifies a previously approved overlapping booking.
test('SCRUM-227: coordinator sees its booking affected by venue unavailability', async ({ page, story }) => {
  const event = await story.event(); const venue = await story.venue(); const booking = await story.book(event, venue, true);
  await story.call('Venue Staff', 'POST', `/api/venues/${venue.venue_id}/unavailability`, {
    starts_at: event.start_datetime, ends_at: event.end_datetime, reason: story.prefix + ' repairs',
  }, 201);
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/venue-bookings/${booking.booking_id}`);
  await expect(page.getByRole('main')).toContainText(/unavailable|cancelled|affected/i);
  const row = await notifications(page, 'Event Coordinator', event.event_name, 'Venue unavailable');
  await expect(row).toContainText(venue.venue_name);
});

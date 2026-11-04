import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-31: a real approved booking makes the venue unavailable to overlapping events.
test('SCRUM-31: confirmed overlapping booking cannot be requested for another event', async ({ page, story }) => {
  const first = await story.event(); const second = await story.event({ event_name: story.prefix + ' second', start_datetime: first.start_datetime, end_datetime: first.end_datetime });
  const venue = await story.venue(); await story.book(first, venue, true);
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/venue-bookings?event_id=${second.event_id}&venue_id=${venue.venue_id}`);
  await expect(page.getByRole('alert').filter({ hasText: /already booked/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Submit booking request', exact: true })).toBeDisabled();
});

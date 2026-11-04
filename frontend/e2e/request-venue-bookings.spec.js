import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-29: one browser request per venue, both linked to the same event.
test('SCRUM-29: coordinator requests two independent venues for one event', async ({ page, story }) => {
  const event = await story.event(); const venues = [await story.venue(), await story.venue()];
  await signIn(page, 'Event Coordinator');
  for (const venue of venues) {
    await page.goto(`/#/venue-bookings?event_id=${event.event_id}&venue_id=${venue.venue_id}`);
    await expect(page.getByRole('main')).toContainText(venue.venue_name);
    await waitForSave(page, '/api/venue-bookings', () => page.getByRole('button', { name: 'Submit booking request', exact: true }).click());
    await expect(page.getByRole('heading', { name: 'Booking request submitted' })).toBeVisible();
  }
  const saved = await admin(`/rest/v1/venue_booking_requests?event_id=eq.${event.event_id}`);
  expect(new Set(saved.map(row => row.venue_id))).toEqual(new Set(venues.map(row => row.venue_id)));
  expect(saved.every(row => row.status === 'pending')).toBe(true);
});

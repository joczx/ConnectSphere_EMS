import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-12: compare a selected event against a real insufficient-capacity venue.
test('SCRUM-12: suitability prevents requesting a venue below event capacity', async ({ page, story }) => {
  const event = await story.event(); const venue = await story.venue({ capacity: 1 });
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/venue-bookings?event_id=${event.event_id}&venue_id=${venue.venue_id}`);
  await expect(page.getByRole('main')).toContainText(event.event_name);
  await expect(page.getByRole('alert').filter({ hasText: /does not meet/ })).toBeVisible();
  await expect(page.getByRole('alert').filter({ hasText: /does not meet/ })).toContainText(/capacity|attendance/i);
  await expect(page.getByRole('button', { name: /Submit booking request/ })).toBeDisabled();
});

import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-223: independently edit one booking's requirements and keep association.
test('SCRUM-223: notes on one venue arrangement do not change the sibling', async ({ page, story }) => {
  const event = await story.event(); const a = await story.venue(); const b = await story.venue();
  const first = await story.book(event, a); const second = await story.book(event, b);
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/venue-bookings?event_id=${event.event_id}&venue_id=${a.venue_id}&booking_id=${first.booking_id}`);
  await page.getByLabel('Venue requirements').fill(story.prefix + ' revised notes');
  await waitForSave(page, `/api/venue-bookings/${first.booking_id}`, () => page.getByRole('button', { name: 'Save changes', exact: true }).click());
  await expect(page.getByRole('heading', { name: 'Booking updated' })).toBeVisible();
  const rows = await admin(`/rest/v1/venue_booking_requests?event_id=eq.${event.event_id}`);
  expect(rows.find(row => row.booking_id === first.booking_id).venue_requirements).toBe(story.prefix + ' revised notes');
  expect(rows.find(row => row.booking_id === second.booking_id).venue_requirements).toBe(story.prefix);
});

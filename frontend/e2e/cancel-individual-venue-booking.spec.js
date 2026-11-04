import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-222 AC1-4: selected booking is cancelled; its sibling and event remain active.
test('SCRUM-222: cancelling one of two bookings leaves the other unchanged', async ({ page, story }) => {
  const event = await story.event(); const a = await story.venue(); const b = await story.venue();
  const first = await story.book(event, a); const second = await story.book(event, b);
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/venue-bookings/${first.booking_id}`);
  await waitForSave(page, `/api/venue-bookings/${first.booking_id}/cancel`, () => page.getByRole('button', { name: 'Cancel booking', exact: true }).click());
  await expect(page.getByRole('main')).toContainText(/cancelled/i);
  const rows = await admin(`/rest/v1/venue_booking_requests?event_id=eq.${event.event_id}`);
  expect(rows.find(row => row.booking_id === first.booking_id).status).toBe('cancelled');
  expect(rows.find(row => row.booking_id === second.booking_id).status).toBe('pending');
  expect((await admin(`/rest/v1/events?event_id=eq.${event.event_id}`))[0].status).toBe('planning');
});

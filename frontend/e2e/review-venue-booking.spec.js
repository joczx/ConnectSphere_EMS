import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-30 AC1-4: approval/rejection via the actual staff review form.
for (const outcome of ['approved', 'rejected']) {
  test(`SCRUM-30: Venue Staff ${outcome} review preserves its reason`, async ({ page, story }) => {
    const event = await story.event(); const venue = await story.venue(); const booking = await story.book(event, venue);
    await signIn(page, 'Venue Staff'); await page.goto(`/#/review-venue-bookings/${booking.booking_id}`);
    await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
    await page.getByLabel('Comments for the Event Coordinator (required when rejecting)').fill(story.prefix + ' decision');
    await waitForSave(page, `/api/venue-bookings/${booking.booking_id}/review`, () => page.getByRole('button', { name: outcome === 'approved' ? 'Approve' : 'Reject', exact: true }).click());
    const [saved] = await admin(`/rest/v1/venue_booking_requests?booking_id=eq.${booking.booking_id}`);
    expect(saved.status).toBe(outcome);
    await page.reload(); await expect(page.getByRole('main')).toContainText(story.prefix + ' decision');
  });
}

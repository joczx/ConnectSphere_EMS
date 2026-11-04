import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-264 AC1-4: submission, staff delivery, outcome and venue identity.
for (const outcome of ['approved', 'rejected']) {
  test(`SCRUM-264: venue booking ${outcome} notifications reach the right users`, async ({ page, story }) => {
    const event = await story.event(); const venue = await story.venue(); const booking = await story.book(event, venue);
    const submitted = await notifications(page, 'Event Coordinator', event.event_name, 'Venue booking request submitted');
    await expect(submitted).toContainText(venue.venue_name);
    const staff = await notifications(page, 'Venue Staff', event.event_name, 'New venue booking request');
    await expect(staff).toContainText(venue.venue_name);
    await story.call('Venue Staff', 'POST', `/api/venue-bookings/${booking.booking_id}/review`, { outcome, comments: story.prefix + ' decision' });
    const result = await notifications(page, 'Event Coordinator', event.event_name, outcome === 'approved' ? 'Venue booking approved' : 'Venue booking rejected');
    await expect(result).toContainText(venue.venue_name);
    await result.getByRole('button').click(); await expect(page).toHaveURL(new RegExp(`#/venue-bookings/${booking.booking_id}$`));
  });
}

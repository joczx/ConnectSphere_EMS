import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-269 AC1-3: both approved and pending affected bookings notify their coordinator.
for (const approved of [false, true]) {
  test(`SCRUM-269: ${approved ? 'approved' : 'pending'} affected booking notifies coordinator`, async ({ page, story }) => {
    const event = await story.event(); const venue = await story.venue(); await story.book(event, venue, approved);
    await story.call('Venue Staff', 'POST', `/api/venues/${venue.venue_id}/unavailability`, {
      starts_at: event.start_datetime, ends_at: event.end_datetime, reason: story.prefix + ' repairs',
    }, 201);
    const note = await notifications(page, 'Event Coordinator', event.event_name, 'Venue unavailable');
    await expect(note).toContainText(venue.venue_name);
    await note.getByRole('button').click(); await expect(page.getByRole('main')).toContainText(event.event_name);
  });
}

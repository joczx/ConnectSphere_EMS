import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-267 AC1/2/4/5: registration, withdrawal and cancellation notifications.
test('SCRUM-267: attendee receives registration, withdrawal and cancellation updates', async ({ page, story }) => {
  const { event, venue } = await story.confirmed();
  const details = { full_name: 'Alex Tan', contact_email: 'alex@example.com', contact_phone: '+65 81234567' };
  await story.call('Attendee', 'POST', `/api/events/${event.event_id}/registrations`, details);
  const registered = await notifications(page, 'Attendee', event.event_name, 'Event registration confirmed');
  await expect(registered).toContainText(venue.venue_name); await expect(registered).toContainText('SGT');
  await story.call('Attendee', 'POST', `/api/events/${event.event_id}/registrations/withdraw`);
  await notifications(page, 'Attendee', event.event_name, 'Event registration withdrawn');
  await story.call('Attendee', 'POST', `/api/events/${event.event_id}/registrations`, details);
  await story.call('Event Coordinator', 'POST', `/api/events/${event.event_id}/cancel`);
  const cancelled = await notifications(page, 'Attendee', event.event_name, 'Event cancelled');
  await cancelled.getByRole('button').click(); await expect(page).toHaveURL(/#\/my-registrations$/);
});

test('SCRUM-267 AC3: waiting-list notice explicitly does not confirm a place', async ({ page, story }) => {
  const { event } = await story.confirmed({ capacity: 1, waitingList: true });
  const filler = await story.temporaryUser('Attendee');
  const details = { full_name: 'Alex Tan', contact_email: 'alex@example.com', contact_phone: '+65 81234567' };
  await story.call(filler, 'POST', `/api/events/${event.event_id}/registrations`, details);
  await story.call('Attendee', 'POST', `/api/events/${event.event_id}/registrations`, details);
  const note = await notifications(page, 'Attendee', event.event_name, 'Added to waiting list');
  await expect(note).toContainText('This does not confirm a place');
});

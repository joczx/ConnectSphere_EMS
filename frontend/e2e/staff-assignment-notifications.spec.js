import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-271 AC1-3: each assigned staff role and its Coordinator receive notifications.
for (const role of ['Venue Staff', 'Technical Support Staff', 'Safety Officer']) {
  test(`SCRUM-271: ${role} receives its event assignment`, async ({ page, story }) => {
    const event = await story.event();
    const note = await notifications(page, role, event.event_name, 'Event assigned to you');
    await note.getByRole('button').click();
    await expect(page).toHaveURL(new RegExp(`#/events/${event.event_id}$`));
    await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
    await notifications(page, 'Event Coordinator', event.event_name, 'Staff assigned to your event');
  });
}

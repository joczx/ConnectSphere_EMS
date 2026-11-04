import { test, expect, admin, notifications } from './story-fixtures.js';

// SCRUM-275 AC1-3: Lead receives organiser/event identity and opens the request.
test('SCRUM-275: new request notification lets Lead inspect the submitted request', async ({ page, story }) => {
  const row = await story.requestEvent();
  const [organiser] = await admin(`/rest/v1/users?user_id=eq.${row.event_organiser_id}`);
  const note = await notifications(page, 'Event Coordinator Lead', row.event_name, 'New event request');
  await expect(note).toContainText(organiser.name);
  await note.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/event-requests/${row.event_request_id}$|#/assign-event-coordinators`));
  await expect(page.getByRole('main')).toContainText(row.event_name);
});

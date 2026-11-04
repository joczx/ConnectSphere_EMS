import { test, expect, admin, signIn, userId } from './story-fixtures.js';

// SCRUM-158 superseded by SCRUM-226: only the Lead initiates reassignment.
test('SCRUM-158: former coordinator-led reassignment is restricted to the Lead workspace', async ({ page, story }) => {
  const event = await story.event();
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/events/${event.event_id}`);
  await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
  await page.goto('/#/reassign-event-coordinators');
  await expect(page).toHaveURL(/#\/home$/);
  expect((await admin(`/rest/v1/events?event_id=eq.${event.event_id}`))[0].event_coordinator_id).toBe(await userId('Event Coordinator'));
});

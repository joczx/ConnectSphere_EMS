import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-37: browser submission of a non-critical change is applied automatically.
test('SCRUM-37: organiser requests a description change and receives confirmation', async ({ page, story }) => {
  const event = await story.event();
  await signIn(page, 'Event Organiser'); await page.goto(`/#/event-change-requests/new?event_id=${event.event_id}`);
  await page.getByLabel('Description').fill(story.prefix + ' new description');
  await page.getByLabel('Reason for this change request').fill(story.prefix + ' correct details');
  await waitForSave(page, `/api/events/${event.event_id}/change-requests`, () => page.getByRole('button', { name: 'Submit change request', exact: true }).click());
  await expect(page.getByRole('heading', { name: 'Change request submitted' })).toBeVisible();
  const [saved] = await admin(`/rest/v1/events?event_id=eq.${event.event_id}`);
  expect(saved.description).toBe(story.prefix + ' new description');
});

import { test, expect, admin, signIn, userId, waitForSave } from './story-fixtures.js';

// SCRUM-219: submitted unassigned queue -> browser assignment -> coordinator access.
test('SCRUM-219: Lead assigns an unassigned request to a coordinator', async ({ page, story }) => {
  const row = await story.requestEvent(); expect(row.event_coordinator_id).toBeNull();
  await signIn(page, 'Event Coordinator Lead'); await page.goto('/#/assign-event-coordinators');
  const card = page.locator('article').filter({ has: page.getByRole('heading', { name: row.event_name, exact: true }) });
  await expect(card).toBeVisible();
  await card.getByLabel('Assign to Event Coordinator').selectOption(await userId('Event Coordinator'));
  await waitForSave(page, `/api/event-requests/${row.event_request_id}/assign-coordinator`, () => card.getByRole('button', { name: 'Assign coordinator', exact: true }).click());
  await expect(card).toHaveCount(0);
  const [saved] = await admin(`/rest/v1/event_request?event_request_id=eq.${row.event_request_id}`);
  expect(saved.event_coordinator_id).toBe(await userId('Event Coordinator'));
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/review-event-requests/${row.event_request_id}`);
  await expect(page.getByRole('heading', { name: row.event_name, exact: true })).toBeVisible();
});

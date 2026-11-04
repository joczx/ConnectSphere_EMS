import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-8 AC1-4: incomplete draft can be saved, reopened and edited.
test('SCRUM-8: save and reopen an incomplete draft without submitting it', async ({ page, story }) => {
  await signIn(page, 'Event Organiser'); await page.goto('/#/event-requests/new');
  await page.getByLabel('Event name').fill(story.prefix);
  const row = await story.trackBrowserRequest(page, () => page.getByRole('button', { name: 'Save draft', exact: true }).click());
  expect(row.status).toBe('draft');
  await page.reload(); await expect(page.getByLabel('Event name')).toHaveValue(story.prefix);
  await page.getByLabel('Purpose').fill('Saved later');
  await waitForSave(page, `/api/event-requests/${row.event_request_id}`, () => page.getByRole('button', { name: 'Save draft', exact: true }).click());
  await page.reload(); await expect(page.getByLabel('Purpose')).toHaveValue('Saved later');
  const [saved] = await admin(`/rest/v1/event_request?event_request_id=eq.${row.event_request_id}`);
  expect(saved.status).toBe('draft'); expect(saved.submitted_at).toBeNull();
});

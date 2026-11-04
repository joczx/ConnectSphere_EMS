import { test, expect, admin, signIn } from './story-fixtures.js';

// SCRUM-20: latest implemented flow lets rejected requests be amended/resubmitted.
test('SCRUM-20: organiser revises and resubmits a rejected event request', async ({ page, story }) => {
  const row = await story.requestEvent(); await story.assign(row); await story.review(row, 'rejected', 'Please revise the description.');
  await signIn(page, 'Event Organiser'); await page.goto(`/#/event-requests/${row.event_request_id}`);
  await page.getByLabel('Description').fill(story.prefix + ' revised');
  await page.getByRole('button', { name: 'Review before submitting' }).click();
  await expect(page.getByRole('heading', { name: 'Review your event request' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm and submit' }).click();
  await expect(page.getByRole('main')).toContainText(/submitted/i);
  const [saved] = await admin(`/rest/v1/event_request?event_request_id=eq.${row.event_request_id}`);
  expect(saved.description).toBe(story.prefix + ' revised'); expect(saved.status).toBe('submitted');
});

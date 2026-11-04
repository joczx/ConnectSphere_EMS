import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-263 AC1/2: assignment produces a real coordinator notification and working link.
test('SCRUM-263: assigned coordinator receives event identity and opens its review', async ({ page, story }) => {
  const row = await story.requestEvent(); await story.assign(row);
  const note = await notifications(page, 'Event Coordinator', row.event_name, 'Event assigned to you');
  await expect(note).toContainText(/assigned/i);
  await note.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/review-event-requests/${row.event_request_id}$`));
  await expect(page.getByRole('heading', { name: row.event_name, exact: true })).toBeVisible();
});

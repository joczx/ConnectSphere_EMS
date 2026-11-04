import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-21 superseded by SCRUM-219: no automatic assignment on submission.
test('SCRUM-21: latest workflow keeps a submitted request unassigned until the Lead assigns it', async ({ page, story }) => {
  const row = await story.requestEvent(); expect(row.event_coordinator_id).toBeNull();
  await story.assign(row);
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/review-event-requests/${row.event_request_id}`);
  await expect(page.getByRole('heading', { name: row.event_name, exact: true })).toBeVisible();
});

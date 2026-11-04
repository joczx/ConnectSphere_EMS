import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-38: critical request decision is persisted and drives the event change.
for (const decision of ['approve', 'reject']) {
  test(`SCRUM-38: coordinator ${decision}s an important change`, async ({ page, story }) => {
    const event = await story.event(); const change = await story.change(event);
    await signIn(page, 'Event Coordinator'); await page.goto(`/#/review-event-change-requests/${change.event_change_request_id}`);
    await expect(page.getByRole('heading', { name: 'Requested changes' })).toBeVisible();
    await page.getByLabel(/Reason for decision/).fill(story.prefix + ' decision');
    await waitForSave(page, `/api/event-change-requests/${change.event_change_request_id}/decision`, () => page.getByRole('button', { name: decision === 'approve' ? 'Approve' : 'Reject', exact: true }).click());
    const [saved] = await admin(`/rest/v1/events?event_id=eq.${event.event_id}`);
    expect(saved.capacity_needed).toBe(decision === 'approve' ? 41 : 40);
    await page.reload(); await expect(page.getByRole('main')).toContainText(story.prefix + ' decision');
  });
}

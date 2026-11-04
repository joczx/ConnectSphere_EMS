import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-9 AC1-5: real assigned request, details, decision and stored outcome.
for (const outcome of ['approved', 'rejected']) {
  test(`SCRUM-9: coordinator ${outcome} decision is saved with comments`, async ({ page, story }) => {
    const row = await story.requestEvent(); await story.assign(row);
    await signIn(page, 'Event Coordinator'); await page.goto(`/#/review-event-requests/${row.event_request_id}`);
    await expect(page.getByRole('heading', { name: row.event_name, exact: true })).toBeVisible();
    await expect(page.getByRole('main')).toContainText(row.description);
    await page.getByLabel('Remarks (required when rejecting)').fill(story.prefix + ' review');
    await waitForSave(page, `/api/event-requests/${row.event_request_id}/review`, () => page.getByRole('button', { name: outcome === 'approved' ? 'Approve' : 'Reject', exact: true }).click());
    const reviews = await admin(`/rest/v1/event_request_review?event_request_id=eq.${row.event_request_id}`);
    expect(reviews.some(review => review.outcome === outcome && review.comments.includes(story.prefix))).toBe(true);
    await page.reload(); await expect(page.getByRole('main')).toContainText(story.prefix + ' review');
  });
}

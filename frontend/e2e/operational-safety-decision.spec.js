import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-215: actual safety decision drives lifecycle and records its reasons.
for (const outcome of ['approved', 'rejected']) {
  test(`SCRUM-215: Safety Officer ${outcome} decision updates event stage`, async ({ page, story }) => {
    const { event } = await story.safety();
    await signIn(page, 'Safety Officer'); await page.goto(`/#/operational-safety-reviews/${event.event_id}`);
    await page.getByLabel(/Remarks/).fill(story.prefix + ' safety decision');
    await waitForSave(page, `/api/operational-safety-reviews/${event.event_id}/decision`, () => page.getByRole('button', { name: outcome === 'approved' ? 'Approve and confirm event' : 'Reject', exact: true }).click());
    const [saved] = await admin(`/rest/v1/events?event_id=eq.${event.event_id}`);
    expect(saved.status).toBe(outcome === 'approved' ? 'confirmed' : 'planning');
    const decisions = await admin(`/rest/v1/operational_safety_decision?event_id=eq.${event.event_id}`);
    expect(decisions.some(row => row.outcome === outcome && row.remarks === story.prefix + ' safety decision')).toBe(true);
    await expect(page).toHaveURL(/#\/operational-safety-reviews$/);
    await expect(page.getByRole('main')).toContainText(new RegExp(`Safety arrangements ${outcome}`));
  });
}

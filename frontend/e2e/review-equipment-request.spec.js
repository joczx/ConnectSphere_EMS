import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-14: accepted/rejected are the implemented status names, not approved.
for (const outcome of ['accepted', 'rejected']) {
  test(`SCRUM-14: technical support ${outcome} decision is visible to coordinator`, async ({ page, story }) => {
    const event = await story.event(); const item = await story.item(); const row = await story.equipmentRequest(event, item);
    if (outcome === 'accepted') await story.reservation(row, item);
    await signIn(page, 'Technical Support Staff'); await page.goto('/#/equipment');
    await page.getByRole('combobox', { name: /^Event/ }).selectOption(String(event.event_id));
    const card = page.locator('article').filter({ hasText: item.equipment_type });
    if (outcome === 'rejected') await card.getByLabel('Reason for rejection').fill(story.prefix + ' unavailable');
    await waitForSave(page, `/api/equipment-request-reviews/${row.equipment_request_id}`, () => card.getByRole('button', { name: outcome === 'accepted' ? 'Accept request' : 'Reject request' }).click());
    const [saved] = await admin(`/rest/v1/equipment_request?equipment_request_id=eq.${row.equipment_request_id}`);
    expect(saved.status).toBe(outcome);
    await signIn(page, 'Event Coordinator'); await page.goto(`/#/events/${event.event_id}`);
    await expect(page.locator('#event-equipment')).toContainText(outcome === 'accepted' ? 'Accepted' : 'Rejected');
  });
}

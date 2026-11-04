import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-266 AC1-4: real equipment request notification, technical delivery, decision.
for (const outcome of ['accepted', 'rejected']) {
  test(`SCRUM-266: equipment ${outcome} result is delivered to its coordinator`, async ({ page, story }) => {
    const event = await story.event(); const item = await story.item(); const row = await story.equipmentRequest(event, item);
    const submitted = await notifications(page, 'Event Coordinator', event.event_name, 'Equipment request submitted');
    await expect(submitted).toContainText(item.equipment_type);
    const technical = await notifications(page, 'Technical Support Staff', event.event_name, 'New equipment request');
    await expect(technical).toContainText('HDMI setup');
    if (outcome === 'accepted') await story.reservation(row, item);
    await story.call('Technical Support Staff', 'POST', `/api/equipment-request-reviews/${row.equipment_request_id}`, {
      outcome, equipment_id: outcome === 'accepted' ? item.equipment_id : null, accepted_quantity: outcome === 'accepted' ? 2 : null, reason: story.prefix + ' unavailable',
    });
    const note = await notifications(page, 'Event Coordinator', event.event_name, `Equipment request ${outcome}`);
    await expect(note).toContainText(item.equipment_type);
  });
}

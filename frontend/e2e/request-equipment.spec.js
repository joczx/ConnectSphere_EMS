import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-13 AC1-4: event-specific request from the actual coordinator form.
test('SCRUM-13: coordinator submits equipment type, quantity and requirements', async ({ page, story }) => {
  const event = await story.event(); const item = await story.item();
  await signIn(page, 'Event Coordinator'); await page.goto('/#/equipment-requests');
  const panel = page.locator('section,article').filter({ has: page.getByRole('heading', { name: event.event_name, exact: true }) }).filter({ has: page.getByRole('button', { name: 'Submit equipment request' }) }).last();
  await panel.getByLabel('Equipment Type').selectOption(item.equipment_type);
  await panel.getByLabel('Quantity').fill('2');
  await panel.getByLabel('Technical requirements').fill(story.prefix + ' HDMI');
  await waitForSave(page, `/api/events/${event.event_id}/equipment-requests`, () => panel.getByRole('button', { name: 'Submit equipment request' }).click());
  const rows = await admin(`/rest/v1/equipment_request?event_id=eq.${event.event_id}`);
  expect(rows).toHaveLength(1); expect(rows[0].quantity).toBe(2); expect(rows[0].technical_requirements).toContain('HDMI');
  await page.reload(); await expect(page.getByRole('main')).toContainText(item.equipment_type);
});

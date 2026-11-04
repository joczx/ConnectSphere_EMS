import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-16: reserve inventory through the browser and verify persisted allocation.
test('SCRUM-16: technical support reserves two units for an event request', async ({ page, story }) => {
  const event = await story.event(); const item = await story.item(); const row = await story.equipmentRequest(event, item);
  await signIn(page, 'Technical Support Staff'); await page.goto('/#/reserved-equipment');
  await page.getByRole('combobox', { name: /^Event/ }).selectOption(String(event.event_id));
  await page.getByLabel('Equipment request').selectOption(String(row.equipment_request_id));
  await page.getByLabel('Equipment model').selectOption(String(item.equipment_id));
  await page.getByLabel('Quantity').fill('2');
  await waitForSave(page, `/api/equipment-request-reviews/${row.equipment_request_id}/reservation`, () => page.getByRole('button', { name: 'Reserve equipment', exact: true }).click());
  const saved = await admin(`/rest/v1/equipment_reservations?event_id=eq.${event.event_id}`);
  expect(saved).toHaveLength(1); expect(saved[0].quantity).toBe(2);
  await expect(page.getByRole('main')).toContainText('Reserved quantity: 2');
});

// SCRUM-16 AC2/5/6: insufficient inventory is refused without a reservation.
test('SCRUM-16: reservation above available quantity is rejected', async ({ page, story }) => {
  const event = await story.event(); const item = await story.item(); const row = await story.equipmentRequest(event, item, 11);
  await signIn(page, 'Technical Support Staff'); await page.goto('/#/reserved-equipment');
  await page.getByRole('combobox', { name: /^Event/ }).selectOption(String(event.event_id));
  await page.getByLabel('Equipment request').selectOption(String(row.equipment_request_id));
  await page.getByLabel('Equipment model').selectOption(String(item.equipment_id));
  await page.getByLabel('Quantity').fill('11');
  await page.getByRole('button', { name: 'Reserve equipment', exact: true }).click();
  await expect(page.getByRole('alert').first()).toBeVisible();
  expect(await admin(`/rest/v1/equipment_reservations?event_id=eq.${event.event_id}`)).toHaveLength(0);
});

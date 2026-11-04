import { test, expect, admin, signIn } from './story-fixtures.js';

// SCRUM-17 AC1-4: change and cancel an owned reservation through the browser.
test('SCRUM-17: reduce quantity then cancel a reservation', async ({ page, story }) => {
  const event = await story.event(); const item = await story.item(); const request = await story.equipmentRequest(event, item);
  await story.reservation(request, item);
  await signIn(page, 'Technical Support Staff'); await page.goto('/#/reserved-equipment');
  const card = page.locator('article').filter({ hasText: event.event_name });
  await card.getByRole('button', { name: 'Edit quantity' }).click();
  await card.getByLabel(/Quantity for/).fill('1');
  await card.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(card).toContainText('Reserved quantity: 1');
  expect((await admin(`/rest/v1/equipment_reservations?event_id=eq.${event.event_id}`))[0].quantity).toBe(1);
  await card.getByRole('button', { name: 'Cancel reservation', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel reservation', exact: true }).click();
  await expect(card).toHaveCount(0);
  expect(await admin(`/rest/v1/equipment_reservations?event_id=eq.${event.event_id}`)).toHaveLength(0);
});

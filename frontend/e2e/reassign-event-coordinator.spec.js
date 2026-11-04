import { test, expect, admin, signIn, userId, waitForSave } from './story-fixtures.js';

// SCRUM-226: Lead chooses another coordinator and the replacement can open the event.
test('SCRUM-226: Lead reassigns an event and replacement gains access', async ({ page, story }) => {
  const event = await story.event(); const replacement = await story.temporaryUser('Event Coordinator');
  await signIn(page, 'Event Coordinator Lead'); await page.goto('/#/reassign-event-coordinators');
  const card = page.locator('article').filter({ has: page.getByRole('heading', { name: event.event_name, exact: true }) });
  await expect(card).toBeVisible(); await card.locator('select').selectOption(replacement.id);
  await waitForSave(page, `/api/coordinator-lead/events/${event.event_id}/coordinator`, () => card.getByRole('button', { name: 'Save reassignment', exact: true }).click());
  expect((await admin(`/rest/v1/events?event_id=eq.${event.event_id}`))[0].event_coordinator_id).toBe(replacement.id);
  await signIn(page, replacement); await page.goto(`/#/events/${event.event_id}`);
  await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
  // Restore ownership so fixture cleanup can use the original coordinator.
  await story.call('Event Coordinator Lead', 'PATCH', `/api/coordinator-lead/events/${event.event_id}/coordinator`, { coordinator_id: await userId('Event Coordinator') });
});

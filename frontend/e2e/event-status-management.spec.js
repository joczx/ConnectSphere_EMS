import { test, expect, admin, signIn } from './story-fixtures.js';

// SCRUM-22: current lifecycle names are Planning -> Pending Safety Checks -> Confirmed.
test('SCRUM-22: safety approval advances the real event status shown to its coordinator', async ({ page, story }) => {
  const { event } = await story.safety();
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/events/${event.event_id}`);
  await expect(page.getByRole('main')).toContainText(/pending safety checks/i);
  await story.call('Safety Officer', 'POST', `/api/operational-safety-reviews/${event.event_id}/decision`, { outcome: 'approved' });
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await expect(page.locator('#event-overview')).toContainText('Confirmed');
  expect((await admin(`/rest/v1/events?event_id=eq.${event.event_id}`))[0].status).toBe('confirmed');
});

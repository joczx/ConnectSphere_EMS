import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-23 AC1/2: a coordinator edits a normal field and the audit records it.
test('SCRUM-23: normal planning edit persists and is shown after reload', async ({ page, story }) => {
  const event = await story.event();
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/events/${event.event_id}`);
  await page.getByRole('button', { name: 'Edit event', exact: true }).click();
  await page.getByLabel('Description').fill(story.prefix + ' edited');
  await waitForSave(page, `/api/events/${event.event_id}`, () => page.getByRole('button', { name: 'Save changes', exact: true }).click());
  await page.reload(); await expect(page.locator('#event-overview')).toContainText(story.prefix + ' edited');
  const activity = await admin(`/rest/v1/event_activity?event_id=eq.${event.event_id}`);
  expect(activity.some(item => item.changes?.description?.to === story.prefix + ' edited')).toBe(true);
});

// SCRUM-23 AC3-6: critical edit warning requires a decision; discard leaves data intact.
for (const confirm of [false, true]) {
  test(`SCRUM-23: ${confirm ? 'confirm' : 'discard'} critical attendance changes`, async ({ page, story }) => {
    const event = await story.event();
    await signIn(page, 'Event Coordinator'); await page.goto(`/#/events/${event.event_id}`);
    await page.getByRole('button', { name: 'Edit event', exact: true }).click();
    await page.getByLabel('Expected attendance').fill('41');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    const warning = page.getByRole('dialog');
    await expect(warning).toContainText(/Critical Edit/);
    if (confirm) {
      await waitForSave(page, `/api/events/${event.event_id}`, () => warning.getByRole('button', { name: 'Confirm and save', exact: true }).click());
    } else await warning.getByRole('button', { name: 'Discard changes', exact: true }).click();
    expect((await admin(`/rest/v1/events?event_id=eq.${event.event_id}`))[0].capacity_needed).toBe(confirm ? 41 : 40);
    const history = await admin(`/rest/v1/event_activity?event_id=eq.${event.event_id}`);
    expect(history.some(row => row.change_type === 'critical_edit')).toBe(confirm);
  });
}

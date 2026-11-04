import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-10 AC1-3: real planning details and latest persisted name after refresh.
for (const role of ['Event Organiser', 'Event Coordinator']) {
  test(`SCRUM-10: ${role} reads latest planning information`, async ({ page, story }) => {
    const event = await story.event();
    await signIn(page, role); await page.goto(`/#/events/${event.event_id}`);
    await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
    await expect(page.locator('#event-overview')).toContainText(event.description);
    const updated = event.event_name + ' updated';
    await story.call('Event Coordinator', 'PATCH', `/api/events/${event.event_id}`, { event_name: updated });
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    await expect(page.getByRole('heading', { name: updated, exact: true })).toBeVisible();
  });
}

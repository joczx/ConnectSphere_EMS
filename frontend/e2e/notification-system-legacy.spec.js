import { test, expect, signIn, notifications } from './story-fixtures.js';

// SCRUM-39 Notification System: legacy umbrella story, current behaviour is SCRUM-261.
// The export has no AC text; use the agreed latest notification-inbox contract.
test('SCRUM-39: stored notification persists across reload and is private to its recipient', async ({ page, story }) => {
  const row = await story.requestEvent();
  await notifications(page, 'Event Organiser', row.event_name, 'Event request submitted');
  await page.reload();
  await expect(page.getByRole('main').getByRole('listitem').filter({ hasText: row.event_name })).toHaveCount(1);
  await signIn(page, 'Attendee');
  const loaded = page.waitForResponse(response => new URL(response.url()).pathname === '/api/notifications' && response.status() === 200 && new URL(response.url()).searchParams.has('page'));
  await page.goto('/#/notifications'); await loaded;
  await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible();
  await expect(page.getByRole('main').getByRole('listitem').filter({ hasText: row.event_name })).toHaveCount(0);
});

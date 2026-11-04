import { test, expect, signIn, notifications } from './story-fixtures.js';

// SCRUM-261: actual generated notifications, popup/full page and read tracking.
test('SCRUM-261: notification popup opens full inbox and marks an item read', async ({ page, story }) => {
  const row = await story.requestEvent();
  await signIn(page, 'Event Organiser');
  await page.locator('summary[aria-label^="Notifications"]').click();
  await expect(page.locator('.account-notifications')).toBeVisible();
  expect(await page.locator('.account-notifications li').count()).toBeLessThanOrEqual(10);
  await page.getByRole('button', { name: 'View all notifications', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible();
  const item = page.getByRole('main').getByRole('listitem').filter({ hasText: row.event_name }).filter({ hasText: 'Event request submitted' });
  await expect(item).toHaveClass(/unread/);
  await item.getByRole('button').click(); await expect(page).toHaveURL(new RegExp(`#/event-requests/${row.event_request_id}$`));
  await page.goto('/#/notifications'); await expect(page.getByRole('main').getByRole('listitem').filter({ hasText: row.event_name }).filter({ hasText: 'Event request submitted' })).not.toHaveClass(/unread/);
  expect(await page.getByRole('main').getByRole('listitem').count()).toBeLessThanOrEqual(20);
});

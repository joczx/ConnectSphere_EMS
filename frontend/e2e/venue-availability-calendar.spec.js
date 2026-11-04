import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-28 AC1-3: calendar views and unavailable slots are rendered for staff.
test('SCRUM-28: authorised user can switch calendar between Day, Week and Month', async ({ page, story }) => {
  const venue = await story.venue();
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/venues/${venue.venue_id}`);
  for (const view of ['Day', 'Week', 'Month']) {
    const button = page.getByRole('button', { name: view, exact: true });
    await button.click(); await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.fc-view-harness')).toBeVisible();
  }
  await expect(page.getByRole('main')).toContainText(/Confirmed|Blocked/);
});

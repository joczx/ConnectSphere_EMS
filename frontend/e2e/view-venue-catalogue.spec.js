import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-25: catalogue and individual details from a real uniquely named venue.
test('SCRUM-25: Venue Staff searches and opens complete venue information', async ({ page, story }) => {
  const venue = await story.venue();
  await signIn(page, 'Venue Staff'); await page.goto(`/#/venues?name=${encodeURIComponent(venue.venue_name)}`);
  await expect(page.getByRole('main')).toContainText(venue.venue_name);
  await page.goto(`/#/venues/${venue.venue_id}`);
  await expect(page.getByRole('heading', { name: venue.venue_name, exact: true })).toBeVisible();
  await expect(page.getByRole('main')).toContainText('200 people');
  await expect(page.getByRole('main')).toContainText('E2E Street');
});

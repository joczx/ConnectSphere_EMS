import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-11 AC2-4: real name search, query change and an empty result.
test('SCRUM-11: coordinator finds a seeded venue and clears an unmatched search', async ({ page, story }) => {
  const venue = await story.venue();
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/venue-search?name=${encodeURIComponent(venue.venue_name)}`);
  await expect(page.getByRole('main')).toContainText(venue.venue_name);
  await page.goto(`/#/venue-search?name=${story.prefix}-does-not-exist`);
  await expect(page.getByRole('main')).toContainText(/no venues/i);
  await page.goto(`/#/venue-search?name=${encodeURIComponent(venue.venue_name)}`);
  await expect(page.getByRole('main')).toContainText(venue.venue_name);
});

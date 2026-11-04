import { test, expect, admin, signIn, fillVenue, waitForSave } from './story-fixtures.js';

// SCRUM-24: a valid venue is created through the staff form and persists.
test('SCRUM-24: Venue Staff creates a complete venue and reviews its saved details', async ({ page, story }) => {
  await signIn(page, 'Venue Staff'); await page.goto('/#/venues/new');
  await fillVenue(page, story.prefix);
  const result = await waitForSave(page, '/api/venues', () => page.getByRole('button', { name: 'Create venue', exact: true }).click());
  story.venues.add(result.venue.venue_id);
  await expect(page).toHaveURL(new RegExp(`#/venues/${result.venue.venue_id}$`));
  await expect(page.getByRole('heading', { name: story.prefix, exact: true })).toBeVisible();
  const [saved] = await admin(`/rest/v1/venues?venue_id=eq.${result.venue.venue_id}`);
  expect(saved.capacity).toBe(200); expect(saved.facilities).toContain('projector'); expect(saved.operating_hours.monday.open).toBe('08:00');
});

// SCRUM-24 AC3: the duplicate name/address combination is rejected.
test('SCRUM-24: duplicate venue identity is not created twice', async ({ page, story }) => {
  const venue = await story.venue();
  await signIn(page, 'Venue Staff'); await page.goto('/#/venues/new');
  await fillVenue(page, venue.venue_name);
  await page.getByRole('button', { name: 'Create venue', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  expect(await admin(`/rest/v1/venues?venue_name=eq.${encodeURIComponent(venue.venue_name)}`)).toHaveLength(1);
});

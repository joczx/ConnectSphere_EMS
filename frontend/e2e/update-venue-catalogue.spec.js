import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-26 AC1-3: partial update persists and preserves unrelated fields.
test('SCRUM-26: Venue Staff updates capacity without changing venue identity', async ({ page, story }) => {
  const venue = await story.venue();
  await signIn(page, 'Venue Staff'); await page.goto(`/#/venues/${venue.venue_id}/edit`);
  await page.getByLabel('Capacity').fill('250');
  await waitForSave(page, `/api/venues/${venue.venue_id}`, () => page.getByRole('button', { name: 'Update venue', exact: true }).click());
  await expect(page).toHaveURL(new RegExp(`#/venues/${venue.venue_id}$`));
  await expect(page.getByRole('main')).toContainText('250 people');
  const [saved] = await admin(`/rest/v1/venues?venue_id=eq.${venue.venue_id}`);
  expect(saved.venue_name).toBe(venue.venue_name); expect(saved.street_name).toBe(venue.street_name); expect(saved.capacity).toBe(250);
});

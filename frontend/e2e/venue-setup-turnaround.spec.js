import { test, expect, admin, signIn, fillVenue, waitForSave } from './story-fixtures.js';

// SCRUM-217 AC1-4: create/update buffered times and reject a negative value.
test('SCRUM-217: setup and turnaround times survive creation and update', async ({ page, story }) => {
  await signIn(page, 'Venue Staff'); await page.goto('/#/venues/new');
  await fillVenue(page, story.prefix);
  await page.getByLabel('Default setup time (minutes)').fill('30');
  await page.getByLabel('Default turnaround time (minutes)').fill('45');
  const result = await waitForSave(page, '/api/venues', () => page.getByRole('button', { name: 'Create venue', exact: true }).click());
  const id = result.venue.venue_id; story.venues.add(id);
  await page.goto(`/#/venues/${id}/edit`);
  await page.getByLabel('Default turnaround time (minutes)').fill('60');
  await waitForSave(page, `/api/venues/${id}`, () => page.getByRole('button', { name: 'Update venue', exact: true }).click());
  const [saved] = await admin(`/rest/v1/venues?venue_id=eq.${id}`);
  expect(saved.default_setup_minutes).toBe(30); expect(saved.default_turnaround_minutes).toBe(60);
  await page.goto(`/#/venues/${id}/edit`);
  await page.getByLabel('Default setup time (minutes)').fill('-1');
  await page.getByRole('button', { name: 'Update venue', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  expect((await admin(`/rest/v1/venues?venue_id=eq.${id}`))[0].default_setup_minutes).toBe(30);
});

import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-27: typed confirmation protects deletion and removed venue is gone.
test('SCRUM-27: exact confirmation is required before deleting an unused venue', async ({ page, story }) => {
  const venue = await story.venue();
  await signIn(page, 'Venue Staff'); await page.goto(`/#/venues/${venue.venue_id}/delete`);
  const remove = page.getByRole('button', { name: 'Delete venue', exact: true });
  await expect(remove).toBeDisabled();
  await page.locator('main input').fill(venue.venue_name);
  await expect(remove).toBeEnabled();
  await waitForSave(page, `/api/venues/${venue.venue_id}`, () => remove.click());
  await expect(page).toHaveURL(/#\/venues$/);
  expect(await admin(`/rest/v1/venues?venue_id=eq.${venue.venue_id}`)).toHaveLength(0);
  story.venues.delete(venue.venue_id);
});

// SCRUM-27: an upcoming approved booking prevents deletion and identifies the event.
test('SCRUM-27: venue with an upcoming event cannot be deleted', async ({ page, story }) => {
  const event = await story.event(); const venue = await story.venue(); await story.book(event, venue, true);
  await signIn(page, 'Venue Staff'); await page.goto(`/#/venues/${venue.venue_id}/delete`);
  await expect(page.getByRole('main')).toContainText(event.event_name);
  await expect(page.getByRole('button', { name: 'Delete venue', exact: true })).toBeDisabled();
  expect(await admin(`/rest/v1/venues?venue_id=eq.${venue.venue_id}`)).toHaveLength(1);
});

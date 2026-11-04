import { test, expect, admin, signIn, inputTime } from './story-fixtures.js';
import { DateTime } from 'luxon';

// SCRUM-225 AC1-3: staff enter an unavailable period and see its recorded reason.
test('SCRUM-225: Venue Staff marks a period unavailable with a reason', async ({ page, story }) => {
  const venue = await story.venue(); const start = DateTime.now().plus({ days: 100 });
  await signIn(page, 'Venue Staff'); await page.goto(`/#/venues/${venue.venue_id}`);
  await page.getByLabel('Start').fill(inputTime(start));
  await page.getByLabel('End').fill(inputTime(start.plus({ hours: 2 })));
  await page.getByLabel('Reason').fill(story.prefix + ' maintenance');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Mark unavailable', exact: true }).click();
  await expect.poll(async () => (await admin(`/rest/v1/venue_blocks?venue_id=eq.${venue.venue_id}`)).length).toBe(1);
  const [block] = await admin(`/rest/v1/venue_blocks?venue_id=eq.${venue.venue_id}`);
  expect(block.reason).toBe(story.prefix + ' maintenance');
  await expect(page.getByRole('main')).toContainText(/unavailable/i);
});

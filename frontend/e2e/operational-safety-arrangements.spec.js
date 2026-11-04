import { test, expect, signIn } from './story-fixtures.js';

// SCRUM-216 AC1/2: assigned safety officer reads actual event/venue arrangements.
test('SCRUM-216: submitted event exposes its operational safety information', async ({ page, story }) => {
  const { event, venue } = await story.safety();
  await signIn(page, 'Safety Officer'); await page.goto('/#/operational-safety-reviews');
  await page.goto(`/#/operational-safety-reviews/${event.event_id}`);
  const details = page.getByRole('region', { name: 'Operational safety arrangements' });
  await expect(details).toContainText(venue.venue_name);
  for (const label of ['Expected attendance','Venue capacity and layout','Emergency access','Accessibility requirements','Equipment placement','Crowd movement','Known venue restrictions']) await expect(details.getByText(label, { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
});

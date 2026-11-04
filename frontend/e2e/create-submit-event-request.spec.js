import { test, expect, signIn, fillRequest } from './story-fixtures.js';

// SCRUM-7 AC1-10: complete form, preview, persist identity/timestamp and feedback.
test('SCRUM-7: organiser reviews and submits a complete event request', async ({ page, story }) => {
  await signIn(page, 'Event Organiser'); await page.goto('/#/event-requests/new');
  await fillRequest(page, story.prefix);
  await page.getByRole('button', { name: 'Review before submitting' }).click();
  await expect(page.getByRole('heading', { name: 'Review your event request' })).toBeVisible();
  const row = await story.trackBrowserRequest(page, () => page.getByRole('button', { name: 'Confirm and submit' }).click());
  await expect(page).toHaveURL(new RegExp(`#/event-requests/${row.event_request_id}$`));
  expect(row.status).toBe('submitted'); expect(row.submitted_at).toBeTruthy();
  await expect(page.getByRole('main')).toContainText(story.prefix);
});

test('SCRUM-7: incomplete details cannot enter the submission preview', async ({ page }) => {
  await signIn(page, 'Event Organiser'); await page.goto('/#/event-requests/new');
  await page.getByRole('button', { name: 'Review before submitting' }).click();
  await expect(page.getByRole('heading', { name: 'Review your event request' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Confirm and submit' })).toHaveCount(0);
  await expect(page).toHaveURL(/event-requests\/new$/);
});

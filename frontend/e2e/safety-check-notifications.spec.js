import { test, expect, notifications } from './story-fixtures.js';
import { DateTime } from 'luxon';

// SCRUM-270 AC1/2: notification identifies event/date and opens assigned safety review.
test('SCRUM-270: Safety Officer opens pending review from its notification', async ({ page, story }) => {
  const { event } = await story.safety();
  const note = await notifications(page, 'Safety Officer', event.event_name, 'Event awaiting safety check');
  await expect(note).toContainText(DateTime.fromISO(event.start_datetime).setZone('Asia/Singapore').toFormat('dd LLL yyyy'));
  await note.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/operational-safety-reviews/${event.event_id}$`));
  await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
});

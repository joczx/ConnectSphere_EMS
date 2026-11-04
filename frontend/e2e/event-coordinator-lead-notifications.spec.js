// SCRUM-275 Notification for Event Coordinator Lead
//   AC1  The Event Coordinator Lead is notified when an event request is successfully submitted.
//   AC2  The notification shows the name of the Event Organiser and the name of the event.
//   AC3  Clicking the notification opens the respective event request, so the Lead can see
//        its full details.
//
// The Organiser submits through the request form. The notification is checked on
// the Lead's Notifications page, and its link on the Assign Event Coordinators page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { eventDate, inputTime, nameOf, notification, removeRequests, signIn } from './helpers.js';

// The link test opens the notification the submission test produced.
test.describe.configure({ mode: 'serial' });

const name = `E2E lead notification ${Date.now()}`;
const starts = DateTime.now().plus({ days: 180 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const ends = starts.plus({ hours: 3 });
let requestId;

test.afterAll(async () => {
  if (requestId) await removeRequests([requestId], name);
});

// E2E-NCL-001 (AC1, AC2): the Organiser submits a request through the form; the Lead is
// told an event request arrived, with the event's name and the Organiser's name.
test('notifies the Lead of a submitted event request', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto('/#/event-requests/new');
  await page.getByLabel('Event name').fill(name);
  await page.getByLabel('Purpose').fill('E2E test');
  await page.getByLabel('Description').fill('Created by event-coordinator-lead-notifications.spec.js; removed afterwards.');
  await page.getByLabel('Start date and time').fill(inputTime(starts));
  await page.getByLabel('End date and time').fill(inputTime(ends));
  await page.getByLabel('Expected attendance').fill('40');
  await page.getByLabel('Room layout').selectOption('theatre');
  await page.getByLabel('No facilities needed').check();
  await page.getByLabel('No equipment needed').check();
  await page.getByRole('button', { name: 'Review before submitting' }).click();
  await page.getByRole('button', { name: 'Confirm and submit' }).click();
  await page.waitForURL(/#\/event-requests\/\d+$/);
  requestId = Number(page.url().split('/').pop());

  await signIn(page, 'Event Coordinator Lead');
  const item = await notification(page, 'New event request', name);
  await expect(item).toContainText(`Event request for ${name} by ${await nameOf('Event Organiser')} `
    + 'received and pending coordinator assignment.');
});

// E2E-NCL-002 (AC3): clicking the notification opens the Assign Event Coordinators page at
// that request, which shows its full details: purpose, Organiser, dates, attendance
// and room layout.
test('opens the submitted request with its full details', async ({ page }) => {
  await signIn(page, 'Event Coordinator Lead');
  const item = await notification(page, 'New event request', name);
  await item.getByRole('button').click();

  await expect(page).toHaveURL(new RegExp(`#/assign-event-coordinators\\?request=${requestId}$`));
  const card = page.locator(`#request-${requestId}`);
  await expect(card).toHaveClass(/highlighted/);
  await expect(card.getByRole('heading', { name })).toBeVisible();
  for (const text of ['E2E test', await nameOf('Event Organiser'), eventDate(starts.toISO()), eventDate(ends.toISO()), '40', 'theatre']) {
    await expect(card).toContainText(text);
  }
});

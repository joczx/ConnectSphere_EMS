// SCRUM-263 Notification for Coordinator Assignment
//   AC1  The Event Coordinator is notified when an event is assigned or reassigned to them.
//   AC2  The notification includes the event name and relevant event information.
//   AC3  The previous Event Coordinator is notified when responsibility is transferred.
//
// The Lead assigns and reassigns through the app's pages. A temporary second
// Event Coordinator takes over the event, so the test Coordinator is the
// previous one. Every notification is checked on the recipient's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  approvedEvent, deleteAccount, nameOf, newAccount, notification, removeRequests, signIn, submitRequest,
} from './helpers.js';

// The transfer test reads what the reassignment test did.
test.describe.configure({ mode: 'serial' });

const name = `E2E coordinator assignment ${Date.now()}`;
const starts = DateTime.now().plus({ days: 110 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
let queued, event, takeover, organiser, lead;

test.beforeAll(async ({ request }) => {
  queued = await submitRequest(request, `${name} request`, starts);
  event = await approvedEvent(request, `${name} event`, starts.plus({ days: 1 }));
  takeover = await newAccount(`E2E Takeover Coordinator ${Date.now()}`, 'Event Coordinator');
  [organiser, lead] = [await nameOf('Event Organiser'), await nameOf('Event Coordinator Lead')];
});

test.afterAll(async () => {
  await removeRequests([queued?.event_request_id, event?.event_request_id].filter(Boolean), name);
  if (takeover) await deleteAccount(takeover);
});

// E2E-NCA-001 (AC1, AC2): the Lead assigns a queued request to the Coordinator, who
// is notified with the event name, its Organiser and who assigned it, and the
// notification opens the request for review.
test('notifies the Coordinator of an event request assigned to them', async ({ page }) => {
  await signIn(page, 'Event Coordinator Lead');
  await page.goto('/#/assign-event-coordinators');
  const card = page.locator('article').filter({ has: page.getByRole('heading', { name: queued.event_name }) });
  await card.getByLabel('Assign to Event Coordinator').selectOption({ label: await nameOf('Event Coordinator') });
  await card.getByRole('button', { name: 'Assign coordinator' }).click();
  await expect(page.getByRole('heading', { name: queued.event_name })).toHaveCount(0);

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Event assigned to you', queued.event_name);
  await expect(item).toContainText(
    `Event request ${queued.event_name} by ${organiser} has been assigned to you by ${lead}, pending review.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/review-event-requests/${queued.event_request_id}$`));
});

// E2E-NCA-002 (AC1, AC2): the Lead reassigns an event in planning to another
// Coordinator, who is notified with the event name, its Organiser, who
// reassigned it and its current stage, and the notification opens the event.
test('notifies the new Coordinator of an event reassigned to them', async ({ page }) => {
  await signIn(page, 'Event Coordinator Lead');
  await page.goto('/#/reassign-event-coordinators');
  const card = page.locator('article').filter({ has: page.getByRole('heading', { name: event.event_name }) });
  await card.getByLabel('Reassign Event Coordinator').selectOption({ label: takeover.name });
  await card.getByRole('button', { name: 'Save reassignment' }).click();
  await expect(page.getByRole('main').getByRole('status').filter({ hasText: /reassigned/i })).toBeVisible();

  await signIn(page, takeover);
  const item = await notification(page, 'Event assigned to you', event.event_name);
  await expect(item).toContainText(
    `Event ${event.event_name} by ${organiser} has been reassigned to you by ${lead}. It is currently in planning.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/events/${event.event_id}$`));
});

// E2E-NCA-003 (AC3): the previous Coordinator is told the event moved, to whom and
// by whom, and the notification opens their events list, since they can no
// longer manage that event.
test('notifies the previous Coordinator that the event was transferred', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Event reassigned', event.event_name);
  await expect(item).toContainText(
    `Event ${event.event_name} by ${organiser} has been reassigned from you to ${takeover.name} by ${lead}.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(/#\/events$/);
});

// SCRUM-262 Notification for Event Requests
//   AC1  A confirmation notification is sent to the Event Organiser when an event
//        request is successfully submitted.
//   AC2  The Event Organiser is notified when the request is approved or rejected.
//
// The Organiser submits through the request form; the Lead's assignment and the
// Coordinator's decision are arranged through the API, since they are other
// users' steps. Every notification is checked on the Organiser's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { admin, apiAs, inputTime, signIn, userId } from './helpers.js';

// The approval test continues the request the submission test made.
test.describe.configure({ mode: 'serial', timeout: 60_000 });

const name = `E2E request notification ${Date.now()}`;
const starts = DateTime.now().plus({ days: 90 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const created = [];

test.afterAll(async () => {
  for (const id of created) {
    await admin(`/rest/v1/events?event_request_id=eq.${id}`, { method: 'DELETE' });
    await admin(`/rest/v1/event_request?event_request_id=eq.${id}`, { method: 'DELETE' });
  }
  await admin(`/rest/v1/notifications?body=like.*${encodeURIComponent(name)}*`, { method: 'DELETE' });
});

async function decide(request, id, outcome, comments) {
  await apiAs(request, 'Event Coordinator Lead', 'POST', `/api/event-requests/${id}/assign-coordinator`,
    { coordinator_id: await userId('Event Coordinator') });
  await apiAs(request, 'Event Coordinator', 'POST', `/api/event-requests/${id}/review`,
    { outcome, ...(comments ? { comments } : {}) });
}

async function openNotification(page, title, eventName) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const firstPageResponse = page.waitForResponse(response =>
      response.url().includes('/api/notifications?page=1')
      && response.request().method() === 'GET');
    await page.goto('/#/notifications?page=1');
    expect((await firstPageResponse).status()).toBe(200);

    while (true) {
      const item = page.getByRole('main').getByRole('listitem')
        .filter({ has: page.getByText(title, { exact: true }) })
        .filter({ hasText: eventName });
      if (await item.count()) {
        await expect(item).toHaveCount(1);
        return item;
      }
      const next = page.getByRole('button', { name: 'Next' });
      if (!await next.count() || await next.isDisabled()) break;
      const nextPageResponse = page.waitForResponse(response =>
        response.url().includes('/api/notifications?page=')
        && response.request().method() === 'GET');
      await next.click();
      expect((await nextPageResponse).status()).toBe(200);
    }
    await page.waitForTimeout(500);
  }
  throw new Error(`Notification "${title}" for "${eventName}" was not found after refreshing.`);
}

// E2E-NER-001 (AC1): the Organiser submits a request through the form and is
// sent a confirmation, which opens the request.
test('confirms a submitted event request', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto('/#/event-requests/new');
  await page.getByLabel('Event name').fill(name);
  await page.getByLabel('Purpose').fill('E2E test');
  await page.getByLabel('Description').fill('Created by event-request-notifications.spec.js; removed afterwards.');
  await page.getByLabel('Start date and time').fill(inputTime(starts));
  await page.getByLabel('End date and time').fill(inputTime(starts.plus({ hours: 3 })));
  await page.getByLabel('Expected attendance').fill('40');
  await page.getByLabel('Room layout').selectOption('theatre');
  await page.getByLabel('No facilities needed').check();
  await page.getByLabel('No equipment needed').check();
  await page.getByRole('button', { name: 'Review before submitting' }).click();
  const [submission] = await Promise.all([
    page.waitForResponse(response => response.url().endsWith('/api/event-requests')
      && response.request().method() === 'POST'),
    page.getByRole('button', { name: 'Confirm and submit' }).click(),
  ]);
  expect(submission.status()).toBe(201);
  await page.waitForURL(/#\/event-requests\/\d+$/);
  const id = Number(page.url().split('/').pop());
  created.push(id);

  const item = await openNotification(page, 'Event request submitted', name);
  await expect(item).toContainText(`Your event request ${name} has been submitted and is awaiting review.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/event-requests/${id}$`));
});

// E2E-NER-002 (AC2): when the Coordinator approves the request, the Organiser is
// notified, and the notification opens the new event.
test('notifies the Organiser that the request was approved', async ({ page, request }) => {
  const id = created[0];
  await decide(request, id, 'approved');
  const [event] = await admin(`/rest/v1/events?select=event_id&event_request_id=eq.${id}`);

  await signIn(page, 'Event Organiser');
  const item = await openNotification(page, 'Event request approved', name);
  await expect(item).toContainText(`Your event request ${name} has been approved by`);
  await expect(item).toContainText('It is now in planning.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/events/${event.event_id}$`));
});

// E2E-NER-003 (AC2): when the Coordinator rejects a request, the Organiser is
// notified with the reason, and the notification opens the request.
test('notifies the Organiser that the request was rejected, with the reason', async ({ page, request }) => {
  const rejectedName = `${name} rejected`;
  const { event_request: row } = await apiAs(request, 'Event Organiser', 'POST', '/api/event-requests', {
    event_name: rejectedName, purpose: 'E2E test', description: 'Created by event-request-notifications.spec.js.',
    event_organiser_id: await userId('Event Organiser'),
    start_datetime: starts.plus({ days: 1 }).toISO(), end_datetime: starts.plus({ days: 1, hours: 3 }).toISO(),
    capacity_needed: 40, room_layout: 'theatre', required_facilities: [], equipment_requirements: [],
  });
  created.push(row.event_request_id);
  await decide(request, row.event_request_id, 'rejected', 'The hall is closed for repairs.');

  await signIn(page, 'Event Organiser');
  const item = await openNotification(page, 'Event request rejected', rejectedName);
  await expect(item).toContainText(`Your event request ${rejectedName} has been rejected by`);
  await expect(item).toContainText('Reason: The hall is closed for repairs.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/event-requests/${row.event_request_id}$`));
});

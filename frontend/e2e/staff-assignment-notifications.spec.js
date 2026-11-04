// SCRUM-271 Notification for Staff Assignment
//   AC1  Venue Staff, Technical Support Staff and Safety Officers are notified when an
//        event is assigned to them.
//   AC2  The notification includes the event name and relevant event information.
//   AC3  The Coordinator is informed when staff are assigned to their event.
//
// Staff are assigned automatically when the Coordinator approves the event request,
// which they do on its review page. The request is submitted and assigned before
// the tests. Every notification is checked on the recipient's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  admin, apiAs, nameOf, notification, notifiedTime, removeRequests, signIn, submitRequest, userId,
} from './helpers.js';

// The staff tests read what the approval in the first test did.
test.describe.configure({ mode: 'serial' });

const name = `E2E staff assignment ${Date.now()}`;
const starts = DateTime.now().plus({ days: 170 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const STAFF = [
  ['Venue Staff', 'Venue Staff', 'venue_staff_id'],
  ['Technical Support Staff', 'Technical Support', 'technical_support_id'],
  ['Safety Officer', 'Safety Officer', 'safety_officer_id'],
];
let submitted, event;

test.beforeAll(async ({ request }) => {
  submitted = await submitRequest(request, name, starts);
  await apiAs(request, 'Event Coordinator Lead', 'POST', `/api/event-requests/${submitted.event_request_id}/assign-coordinator`,
    { coordinator_id: await userId('Event Coordinator') });
});

test.afterAll(async () => {
  if (submitted) await removeRequests([submitted.event_request_id], name);
});

// E2E-NSA-001 (AC3): the Coordinator approves the request, which assigns the staff;
// the Coordinator is told who was assigned in each role, and it opens the event.
test('informs the Coordinator which staff were assigned to their event', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/review-event-requests/${submitted.event_request_id}`);
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  // The page asks for confirmation, since the decision cannot be changed.
  await page.getByRole('button', { name: 'Approve request' }).click();
  await expect.poll(async () => (await admin(`/rest/v1/events?select=*&event_request_id=eq.${submitted.event_request_id}`)).length)
    .toBe(1);
  [event] = await admin(`/rest/v1/events?select=*&event_request_id=eq.${submitted.event_request_id}`);
  // Each staff test signs in as that role's test account, so it must be the one assigned.
  for (const [role, , column] of STAFF) expect(event[column], `approval assigned another ${role}`).toBe(await userId(role));

  const assigned = (await Promise.all(STAFF.map(async ([role, label]) => `${label} ${await nameOf(role)}`))).join(', ');
  const item = await notification(page, 'Staff assigned to your event', name);
  await expect(item).toContainText(`Staff assigned to ${name}: ${assigned}.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/events/${event.event_id}$`));
});

for (const [index, [role, label]] of STAFF.entries()) {
  // E2E-NSA-002 to E2E-NSA-004 (AC1, AC2): each assigned staff member is told the event
  // name, its Organiser, dates and times, their role and the Event Coordinator, and
  // the notification opens the event.
  test(`E2E-NSA-00${index + 2} notifies the ${role} assigned to the event`, async ({ page }) => {
    await signIn(page, role);
    const item = await notification(page, 'Event assigned to you', name);
    await expect(item).toContainText(`Event ${name} by ${await nameOf('Event Organiser')} `
      + `(${notifiedTime(event.start_datetime)} – ${notifiedTime(event.end_datetime)} SGT) has been assigned to you `
      + `as ${label}. Event Coordinator: ${await nameOf('Event Coordinator')}.`);
    await item.getByRole('button').click();
    await expect(page).toHaveURL(new RegExp(`#/events/${event.event_id}$`));
  });
}

// SCRUM-265 Notification for Event Change Request
//   AC1  The Event Organiser is sent a confirmation when a change request is submitted.
//   AC2  The assigned Event Coordinator is notified when a change request is submitted.
//   AC3  The notification includes the details of the requested changes.
//   AC4  The Event Organiser is notified when the change request is approved or rejected.
//   AC5  If approved, the relevant users are notified of the approved changes.
//
// The Organiser submits and the Coordinator decides through the app's pages; the
// event in planning is arranged before the tests. Every notification is checked
// on the recipient's Notifications page. "Relevant users" (AC5) are the event's
// assigned staff; the Venue Staff test account is checked.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  admin, apiAs, approvedEvent, nameOf, notification, removeRequests, signIn, userId,
} from './helpers.js';

// Each step continues the change requests the one before made.
test.describe.configure({ mode: 'serial' });

const name = `E2E change request ${Date.now()}`;
const starts = DateTime.now().plus({ days: 120 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const approvedChange = 'Expected attendance: 40 → 60';
let event, changeId;

test.beforeAll(async ({ request }) => {
  event = await approvedEvent(request, name, starts);
  // AC5 is checked as the event's Venue Staff, so it must be the test account.
  expect(event.venue_staff_id, 'approval assigned another Venue Staff user').toBe(await userId('Venue Staff'));
});

test.afterAll(async () => {
  if (event) await removeRequests([event.event_request_id], name);
});

async function latestChangeId() {
  const [row] = await admin(`/rest/v1/event_change_request?select=event_change_request_id`
    + `&event_id=eq.${event.event_id}&order=submitted_at.desc&limit=1`);
  return row.event_change_request_id;
}

async function decide(page, id, decision, reason) {
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/review-event-change-requests/${id}`);
  if (reason) await page.getByLabel(/Reason for decision/).fill(reason);
  await page.getByRole('button', { name: decision === 'approve' ? 'Approve' : 'Reject', exact: true }).click();
  // The page asks for confirmation before the decision is saved.
  await page.getByRole('button', { name: decision === 'approve' ? 'Approve and apply' : 'Reject request' }).click();
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0);
}

// E2E-NCR-001 (AC1, AC3): the Organiser asks for more attendees and is sent a
// confirmation that lists the change and says it is awaiting review.
test('confirms a submitted change request to the Organiser', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto(`/#/event-change-requests/new?event_id=${event.event_id}`);
  await page.getByLabel('Expected attendance').fill('60');
  await page.getByLabel('Reason for this change request').fill('More guests have confirmed.');
  // Attendance needs the Coordinator's review. (The page only asks the Organiser to
  // confirm such a change once the event is confirmed; this one is in planning.)
  await page.getByRole('button', { name: 'Submit change request' }).click();
  await expect(page.getByRole('main').getByRole('status').filter({ hasText: 'Change request submitted' })).toBeVisible();
  changeId = await latestChangeId();

  const item = await notification(page, 'Event change request submitted', name);
  await expect(item).toContainText(
    `Your change request for ${name} has been submitted and is awaiting review. Changes: ${approvedChange}`);
});

// E2E-NCR-002 (AC2, AC3): the event's Coordinator is told who asked for which
// change and why, and the notification opens the request for review.
test('notifies the assigned Coordinator of the change request', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'New event change request', name);
  await expect(item).toContainText(
    `${await nameOf('Event Organiser')} requested changes to ${name}. Changes: ${approvedChange}. `
    + 'Reason: More guests have confirmed.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(new RegExp(`#/review-event-change-requests/${changeId}$`));
});

// E2E-NCR-003 (AC4, AC5): the Coordinator approves; the Organiser is told it was
// approved and applied, and the event's Venue Staff are told what changed.
test('notifies the Organiser and the event staff of an approval', async ({ page }) => {
  await decide(page, changeId, 'approve');

  await signIn(page, 'Event Organiser');
  const outcome = await notification(page, 'Event change request approved', name);
  await expect(outcome).toContainText(
    `Your change request for ${name} has been approved by ${await nameOf('Event Coordinator')}. The event has been updated.`);

  await signIn(page, 'Venue Staff');
  const staff = await notification(page, 'Event changes approved', name);
  await expect(staff).toContainText(`Changes to ${name} have been approved. Changes: ${approvedChange}`);
});

// E2E-NCR-004 (AC4): the Coordinator rejects a further change with a reason; the
// Organiser is told it was rejected, by whom and why.
test('notifies the Organiser of a rejection with the reason', async ({ page, request }) => {
  const [current] = await admin(`/rest/v1/events?select=updated_at&event_id=eq.${event.event_id}`);
  await apiAs(request, 'Event Organiser', 'POST', `/api/events/${event.event_id}/change-requests`, {
    reason: 'Even more guests.', proposed_values: { capacity_needed: 80 },
    expected_event_updated_at: current.updated_at,
  });
  await decide(page, await latestChangeId(), 'reject', 'The venue cannot hold 80 people.');

  await signIn(page, 'Event Organiser');
  const item = await notification(page, 'Event change request rejected', name);
  await expect(item).toContainText(
    `Your change request for ${name} has been rejected by ${await nameOf('Event Coordinator')}. `
    + 'Reason: The venue cannot hold 80 people.');
});

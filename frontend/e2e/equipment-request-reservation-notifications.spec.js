// SCRUM-266 Notification for Equipment Request and Reservation
//   AC1  The Event Coordinator is sent a confirmation when an equipment request is submitted.
//   AC2  The relevant Technical Support Staff are notified of a new equipment request.
//   AC3  The notification includes the relevant details of the equipment request.
//   AC4  The Event Coordinator is notified when the request is Rejected or Accepted.
//
// The Coordinator requests and Technical Support decide through the app's pages;
// the event in planning and two catalogue items are arranged before the tests,
// and the reservation an acceptance needs is made through the API. Every
// notification is checked on the recipient's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import {
  admin, apiAs, approvedEvent, nameOf, newEquipment, notification, removeEquipment, removeRequests,
  signIn, userId,
} from './helpers.js';

// Each step continues the requests the one before made.
test.describe.configure({ mode: 'serial' });

const name = `E2E equipment request ${Date.now()}`;
const starts = DateTime.now().plus({ days: 130 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
const sgt = value => DateTime.fromISO(value).setZone('Asia/Singapore').toFormat('dd LLL yyyy HH:mm');
let event, accepted, rejected, acceptedId, rejectedId;

test.beforeAll(async ({ request }) => {
  event = await approvedEvent(request, name, starts);
  // AC2 is checked as the event's Technical Support, so it must be the test account.
  expect(event.technical_support_id, 'approval assigned another Technical Support user')
    .toBe(await userId('Technical Support Staff'));
  accepted = await newEquipment('Projector');
  rejected = await newEquipment('Camera');
});

test.afterAll(async ({ request }) => {
  await removeEquipment(request, event, [accepted, rejected]);
  if (event) await removeRequests([event.event_request_id], name);
});

const requestFor = async item => (await admin('/rest/v1/equipment_request?select=equipment_request_id'
  + `&event_id=eq.${event.event_id}&equipment_type=eq.${encodeURIComponent(item.equipment_type)}`))[0].equipment_request_id;

// The request's card on Technical Support's Equipment Requests page.
async function reviewCard(page, item) {
  await signIn(page, 'Technical Support Staff');
  await page.goto(`/#/equipment?event_id=${event.event_id}`);
  return page.locator('article').filter({ has: page.getByRole('heading', { name: item.equipment_type }) });
}

// E2E-NEQ-001 (AC1, AC3): the Coordinator requests 2 projectors and is sent a
// confirmation with the quantity, equipment, event and pending status.
test('confirms a submitted equipment request to the Coordinator', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/equipment-requests?event_id=${event.event_id}`);
  const form = page.locator('form').filter({ hasText: 'New equipment request' });
  await form.getByLabel('Equipment Type').selectOption(accepted.equipment_type);
  await form.getByLabel('Quantity').fill('2');
  await form.getByLabel('Technical requirements').fill('HDMI input for a laptop');
  await form.getByRole('button', { name: 'Submit equipment request' }).click();
  await expect(page.getByRole('heading', { name: accepted.equipment_type, level: 3 })).toBeVisible();
  acceptedId = await requestFor(accepted);

  const item = await notification(page, 'Equipment request submitted', name, accepted.equipment_type);
  await expect(item).toContainText(`Your equipment request for 2 × ${accepted.equipment_type} for ${name} `
    + 'has been submitted. Status: pending Technical Support review.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(/#\/equipment-requests$/);
});

// E2E-NEQ-002 (AC2, AC3): the event's Technical Support are told who requested
// what, for which event and when, with the technical requirements and status.
test('notifies the event\'s Technical Support of the new request', async ({ page }) => {
  await signIn(page, 'Technical Support Staff');
  const item = await notification(page, 'New equipment request', name, accepted.equipment_type);
  await expect(item).toContainText(`${await nameOf('Event Coordinator')} requested 2 × ${accepted.equipment_type} `
    + `for ${name} (${sgt(event.start_datetime)} – ${sgt(event.end_datetime)} SGT). `
    + 'Technical requirements: HDMI input for a laptop. Status: pending review.');
  await item.getByRole('button').click();
  await expect(page).toHaveURL(/#\/equipment$/);
});

// E2E-NEQ-003 (AC4): Technical Support reject a second request with a reason; the
// Coordinator is told it was rejected, by whom and why.
test('notifies the Coordinator that a request was rejected', async ({ page, request }) => {
  await apiAs(request, 'Event Coordinator', 'POST', `/api/events/${event.event_id}/equipment-requests`,
    { equipment_type: rejected.equipment_type, quantity: 1 });
  rejectedId = await requestFor(rejected);
  const card = await reviewCard(page, rejected);
  await card.getByLabel('Reason for rejection').fill('No cameras are free that week.');
  await card.getByRole('button', { name: 'Reject request' }).click();
  await expect(card.getByRole('button', { name: 'Reject request' })).toHaveCount(0);

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Equipment request rejected', name, rejected.equipment_type);
  await expect(item).toContainText(`Your equipment request for 1 × ${rejected.equipment_type} for ${name} `
    + `has been rejected by ${await nameOf('Technical Support Staff')}. Reason: No cameras are free that week.`);
});

// E2E-NEQ-004 (AC4): Technical Support reserve the projectors and accept the first
// request; the Coordinator is told it was accepted, and by whom.
test('notifies the Coordinator that a request was accepted', async ({ page, request }) => {
  await apiAs(request, 'Technical Support Staff', 'POST', `/api/equipment-request-reviews/${acceptedId}/reservation`,
    { equipment_id: accepted.equipment_id, quantity: 2 });
  const card = await reviewCard(page, accepted);
  await card.getByRole('button', { name: 'Accept request' }).click();
  await expect(card.getByRole('button', { name: 'Accept request' })).toHaveCount(0);

  await signIn(page, 'Event Coordinator');
  const item = await notification(page, 'Equipment request accepted', name, accepted.equipment_type);
  await expect(item).toContainText(`Your equipment request for 2 × ${accepted.equipment_type} for ${name} `
    + `has been accepted by ${await nameOf('Technical Support Staff')}.`);
});

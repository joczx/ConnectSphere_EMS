// SCRUM-267 Notification for Attendees Registration
//   AC1  A confirmation notification is sent when an Attendee successfully registers.
//   AC2  The notification includes the event name, date, time, and venue when available.
//   AC3  If the event is full and a waiting list is enabled, the Attendee is told they
//        were added to the waiting list instead of receiving a confirmed registration.
//   AC4  A notification is sent if the event is cancelled.
//   AC5  A confirmation notification is sent when the registration is withdrawn.
//
// The Attendee registers and withdraws through the Event registration page. The
// confirmed events come from global-setup.js (notify_register, notify_waitlist,
// notify_cancel); the Organiser's cancellation is made through the API. Every
// notification is checked on the Attendee's Notifications page.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { apiAs, eventCard, fixtures, notification, signIn } from './helpers.js';

const data = fixtures();
// The withdrawal test withdraws the registration the first test made.
test.describe.configure({ mode: 'serial' });

// "<event> (05 Jan 2027 10:00 – 05 Jan 2027 13:00 SGT) at <venue>", as notifications write it.
const sgt = value => DateTime.fromISO(value).setZone('Asia/Singapore').toFormat('dd LLL yyyy HH:mm');
const details = event =>
  `${event.event_name} (${sgt(event.start_datetime)} – ${sgt(event.end_datetime)} SGT) at ${event.venue_name}`;

async function register(page, event) {
  await signIn(page, 'Attendee');
  await page.goto('/#/event-registration');
  const card = eventCard(page, event);
  await card.getByRole('button', { name: /^Register/ }).click();
  await card.getByLabel('Full name').fill('E2E Attendee');
  await card.getByLabel('Contact email').fill('e2e.attendee@connectsphere.invalid');
  await card.getByLabel('Contact phone').fill('+65 6123 4567');
  await card.getByRole('button', { name: 'Submit registration' }).click();
  await expect(card.getByRole('button', { name: 'Withdraw registration' })).toBeVisible();
}

// E2E-NAR-001 (AC1, AC2): the Attendee registers and is sent a confirmation with the
// event name, its date and times, and its venue; it opens My registrations.
test('confirms a successful registration with the event details', async ({ page }) => {
  await register(page, data.notify_register);

  const item = await notification(page, 'Event registration confirmed', data.notify_register.event_name);
  await expect(item).toContainText(`Your registration for ${details(data.notify_register)} is confirmed.`);
  await item.getByRole('button').click();
  await expect(page).toHaveURL(/#\/my-registrations$/);
});

// E2E-NAR-002 (AC3): the only place is taken and the waiting list is on, so the
// Attendee is told they joined the waiting list and that no place is confirmed.
test('tells the Attendee they joined the waiting list instead', async ({ page }) => {
  await register(page, data.notify_waitlist);

  const item = await notification(page, 'Added to waiting list', data.notify_waitlist.event_name);
  await expect(item).toContainText(`${details(data.notify_waitlist)} is full, so you have been added to its `
    + 'waiting list instead. This does not confirm a place at the event.');
  await expect(page.getByRole('main').getByRole('listitem')
    .filter({ hasText: 'Event registration confirmed' }).filter({ hasText: data.notify_waitlist.event_name }))
    .toHaveCount(0);
});

// E2E-NAR-003 (AC4): the Organiser cancels an event the Attendee registered for,
// and the Attendee is told their registration no longer applies.
test('notifies the Attendee that the event was cancelled', async ({ page, request }) => {
  await apiAs(request, 'Event Organiser', 'POST', `/api/events/${data.notify_cancel.event_id}/cancel`, {});

  await signIn(page, 'Attendee');
  const item = await notification(page, 'Event cancelled', data.notify_cancel.event_name);
  await expect(item).toContainText(
    `${details(data.notify_cancel)} has been cancelled, so your registration no longer applies.`);
});

// E2E-NAR-004 (AC5): the Attendee withdraws the registration made in E2E-NAR-001 and
// is sent a confirmation that it was withdrawn.
test('confirms a withdrawn registration', async ({ page }) => {
  await signIn(page, 'Attendee');
  await page.goto('/#/event-registration');
  const card = eventCard(page, data.notify_register);
  await card.getByRole('button', { name: 'Withdraw registration' }).click();
  await expect(card).toContainText('Your registration has been withdrawn.');

  const item = await notification(page, 'Event registration withdrawn', data.notify_register.event_name);
  await expect(item).toContainText(`Your registration for ${details(data.notify_register)} has been withdrawn.`);
});

// SCRUM-33 Register for an Event
//   AC1  Attendees can register for an event that is open for registration.
//   AC2  Attendees can provide their required personal and contact details.
//   AC3  All mandatory registration information is validated.
//   AC4  Registration is prevented when the event has reached its capacity.
//   AC5  Successful registration is confirmed and a notification email is sent.
import { test, expect } from '@playwright/test';
import { admin, eventCard, fixtures, signIn, userId } from './helpers.js';

const data = fixtures();
// The tests share one event: the refused attempt must come before the registration.
test.describe.configure({ mode: 'serial' });

async function openForm(page, event) {
  await signIn(page, 'Attendee');
  await page.goto('/#/event-registration');
  const card = eventCard(page, event);
  await card.getByRole('button', { name: /^Register/ }).click();
  return card;
}

async function fillDetails(card, phone = '+65 6123 4567') {
  await card.getByLabel('Full name').fill('E2E Attendee');
  await card.getByLabel('Contact email').fill('e2e.attendee@connectsphere.invalid');
  await card.getByLabel('Contact phone').fill(phone);
}

async function registrationOf(event) {
  const attendee = await userId('Attendee');
  return admin(`/rest/v1/event_registration?select=status&event_id=eq.${event.event_id}&attendee_id=eq.${attendee}`);
}

// E2E-REG-001 (AC3): an empty form is not submitted, and an invalid phone number
// is refused with a message; neither registers the Attendee.
test('refuses missing or invalid registration details', async ({ page }) => {
  const card = await openForm(page, data.open);
  const submit = card.getByRole('button', { name: 'Submit registration' });

  await submit.click();
  await expect(card.getByLabel('Full name')).toBeFocused();

  await fillDetails(card, 'not a phone');
  await submit.click();

  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  expect(await registrationOf(data.open)).toEqual([]);
});

// E2E-REG-002 (AC1, AC2, AC5): the Attendee enters their details and registers;
// the page confirms it and a confirmation email is queued for them.
test('registers with personal and contact details and confirms it', async ({ page }) => {
  const card = await openForm(page, data.open);
  await fillDetails(card);
  await card.getByRole('button', { name: 'Submit registration' }).click();

  await expect(page.getByRole('main').getByRole('status').filter({ hasText: 'You are registered' }))
    .toHaveText('You are registered for the event. A confirmation email has been queued.');
  expect(await registrationOf(data.open)).toEqual([{ status: 'registered' }]);
  const attendee = await userId('Attendee');
  const email = await admin('/rest/v1/registration_email_outbox?select=event_id'
    + `&event_id=eq.${data.open.event_id}&attendee_id=eq.${attendee}`);
  expect(email).toHaveLength(1);
});

// E2E-REG-003 (AC4): registering for an event at capacity, with no waiting list,
// is refused with a message.
test('prevents registration when the event is full', async ({ page }) => {
  const card = await openForm(page, data.full);
  await expect(card).toContainText('Available places: 0');
  await fillDetails(card);
  await card.getByRole('button', { name: 'Submit registration' }).click();

  await expect(page.getByRole('main').getByRole('alert'))
    .toHaveText('This event is full. The waiting list is disabled.');
  expect(await registrationOf(data.full)).toEqual([]);
});

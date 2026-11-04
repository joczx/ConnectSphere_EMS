// SCRUM-35 Withdraw Event Registration
//   AC1  Attendees can withdraw their registration before the event start time.
//   AC2  Attendees cannot withdraw at or after the event start time.
//   AC3  The registration status is updated after a successful withdrawal.
//   AC4  The withdrawal is confirmed.
//   AC5  The available event capacity is updated after a withdrawal.
//
// AC2 has no end-to-end test: every test event starts weeks ahead, and a
// confirmed event's dates cannot be changed. frontend/tests/registration-db.mjs
// covers it against the database rules.
import { test, expect } from '@playwright/test';
import { eventCard, fixtures, signIn } from './helpers.js';

const data = fixtures();

// E2E-WDR-001 (AC1, AC3, AC4, AC5): the Attendee withdraws before the event starts;
// the page confirms it, the place is released and the status becomes Withdrawn.
test('withdraws a registration, confirms it and releases the place', async ({ page }) => {
  await signIn(page, 'Attendee');
  await page.goto('/#/event-registration');
  const card = eventCard(page, data.withdraw);
  await expect(card).toContainText(
    `${data.withdraw.capacity_needed - 1} available places / ${data.withdraw.capacity_needed} total`,
  );

  await card.getByRole('button', { name: 'Withdraw registration' }).click();

  await expect(page.getByRole('main').getByRole('alert'))
    .toContainText('Your registration has been successfully withdrawn.');
  await expect(card).toContainText('Your registration has been withdrawn.');
  await expect(card).toContainText(
    `${data.withdraw.capacity_needed} available places / ${data.withdraw.capacity_needed} total`,
  );

  await page.goto('/#/my-registrations');
  await expect(eventCard(page, data.withdraw)).toContainText('Registration status: Withdrawn');
});

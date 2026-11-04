// SCRUM-34 View Registration Status
//   AC1  Attendees can view a list of events they have registered for.
//   AC2  The current registration status is shown, such as Confirmed, Waitlisted or Withdrawn.
//   AC3  Relevant event information is shown: name, date, time and venue.
//   AC4  An appropriate message is shown when the Attendee has no registration records.
import { test, expect } from '@playwright/test';
import { eventCard, fixtures, registrationDate, signIn } from './helpers.js';

const data = fixtures();

// E2E-MYR-001 (AC1, AC2, AC3): each registration is listed with its status and the
// event's dates, times and venue.
test('lists registrations with status, dates and venue', async ({ page }) => {
  await signIn(page, 'Attendee');
  await page.goto('/#/my-registrations');

  for (const [event, status] of [[data.withdraw, 'Confirmed'], [data.waitlist, 'Waitlisted'],
    [data.cancelled, 'Withdrawn']]) {
    const card = eventCard(page, event);
    await expect(card).toContainText(`Registration status: ${status}`);
    await expect(card).toContainText(registrationDate(event.start_datetime));
    await expect(card).toContainText(registrationDate(event.end_datetime));
    await expect(card).toContainText(event.venue_name);
  }
});

// E2E-MYR-002 (AC4): an Attendee who has never registered is told they have no records.
test('shows a message when there are no registrations', async ({ page }) => {
  await signIn(page, data.empty_attendee);
  await page.goto('/#/my-registrations');

  const emptyState = page.getByRole('status').filter({ hasText: 'registration records' });
  await expect(emptyState.getByRole('heading', { name: 'You have no registration records.' }))
    .toBeVisible();
  await expect(emptyState).toContainText('Browse upcoming events to find something you would like to join.');
});

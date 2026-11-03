// SCRUM-32 View an Event as an Attendee
//   AC1  Attendees can view a list of upcoming events that are open for registration.
//   AC2  Relevant event information is displayed: name, description, date, time,
//        venue and other applicable details.
//   AC3  The latest confirmed event information is displayed.
//   AC4  Events that are cancelled or no longer available for registration are not displayed.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { apiAs, eventCard, fixtures, registrationDate, signIn } from './helpers.js';

const data = fixtures();

test.beforeEach(async ({ page }) => {
  await signIn(page, 'Attendee');
  await page.goto('/#/event-registration');
  await expect(page.getByRole('heading', { name: 'Event registration' })).toBeVisible();
});

// E2E-ATT-001 (AC1): an upcoming confirmed event open for registration is listed,
// and an event still in planning is not.
test('lists an event open for registration and not one in planning', async ({ page }) => {
  await expect(eventCard(page, data.open)).toContainText('Registration is open.');
  await expect(page.getByRole('heading', { name: data.planning.event_name })).toHaveCount(0);
});

// E2E-ATT-002 (AC2): the event's name, description, date and time, and venue are shown.
// Needs supabase/058_attendee_event_venues.sql run in the test project.
test('shows the event name, description, date, time and venue', async ({ page }) => {
  const card = eventCard(page, data.open);
  await expect(card).toContainText(data.open.description);
  await expect(card).toContainText(registrationDate(data.open.start_datetime));
  await expect(card).toContainText(data.open.venue_name);
});

// E2E-ATT-003 (AC3): after the Organiser changes the registration period, the
// Attendee sees the new times.
test('shows the latest event information after it changes', async ({ page, request }) => {
  const opens = DateTime.now().minus({ hours: 1 }).startOf('minute');
  const closes = opens.plus({ days: 2 });
  await apiAs(request, 'Event Organiser', 'PATCH', `/api/events/${data.open.event_id}/registration-period`, {
    registration_opens_at: opens.toUTC().toISO(), registration_closes_at: closes.toUTC().toISO(),
    waiting_list_enabled: false,
  });

  await page.getByRole('button', { name: 'Refresh' }).click();

  await expect(eventCard(page, data.open)).toContainText(`Registration opens: ${registrationDate(opens.toISO())}`);
});

// E2E-ATT-004 (AC4): cancelled and closed events are not displayed.
test('does not display unavailable events', async ({ page }) => {
  await expect(eventCard(page, data.open)).toBeVisible();
  for (const event of [data.cancelled, data.closed]) {
    await expect(page.getByRole('heading', { name: event.event_name })).toHaveCount(0);
  }
});

test('shows a confirmed event before opening with registration disabled', async ({ page }) => {
  const card = eventCard(page, data.not_open);
  await expect(card).toContainText('Registration is not yet open.');
  await expect(card.getByRole('button', { name: /^Register/ })).toBeDisabled();
});

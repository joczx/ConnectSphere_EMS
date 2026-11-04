// SCRUM-157 View confirmed event information
//   AC1  Authorised users can view the confirmed venue, date and time.
//   AC2  Authorised users can view the confirmed equipment and technical support.
//   AC3  The Event Organiser can set the registration open date for the event.
//   AC4  The system only displays Confirmed events (tested as: the Confirmed filter
//        on the Events page lists only confirmed events).
import { test, expect } from '@playwright/test';
import { eventDate, fixtures, signIn } from './helpers.js';

let data;
test.beforeAll(() => { data = fixtures(); });
const ROLES = ['Event Organiser', 'Event Coordinator', 'Venue Staff', 'Technical Support Staff'];

for (const [index, role] of ROLES.entries()) {
  // E2E-CEI-001 to E2E-CEI-004 (AC1, AC2): each authorised role sees the confirmed
  // event's date and time, its venue, and the equipment arranged for it.
  test(`E2E-CEI-00${index + 1} ${role} sees the confirmed arrangements`, async ({ page }) => {
    await signIn(page, role);
    await page.goto(`/#/events/${data.open.event_id}`);

    // Scoped to the page body: the same names also appear in hidden notifications.
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { level: 1, name: data.open.event_name })).toBeVisible();
    await expect(main.getByText(eventDate(data.open.start_datetime)).first()).toBeVisible();
    await expect(main.getByText(eventDate(data.open.end_datetime)).first()).toBeVisible();
    await expect(main.getByText(data.open.venue_name).first()).toBeVisible();
    await expect(main.getByRole('heading', { name: data.open.equipment_type })).toBeVisible();
  });
}

// E2E-CEI-005 (AC3): the Organiser can set registration dates; the Coordinator cannot.
test('only the Organiser can set the registration period', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto(`/#/events/${data.open.event_id}`);
  await expect(page.getByRole('button', { name: 'Set or update registration' })).toBeVisible();

  await signIn(page, 'Event Coordinator');
  await page.goto(`/#/events/${data.open.event_id}`);
  await expect(page.getByRole('heading', { name: 'Registration period' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Set or update registration' })).toHaveCount(0);
});

// E2E-CEI-006 (AC4): the Confirmed filter lists the confirmed event and not one in planning.
test('the Confirmed filter shows only confirmed events', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto('/#/events');

  // The filter buttons read "<status> <count>", e.g. "Confirmed 1".
  await page.getByRole('button', { name: /^Confirmed \d+$/ }).click();

  await expect(page.getByRole('heading', { name: data.open.event_name })).toBeVisible();
  await expect(page.getByRole('heading', { name: data.planning.event_name })).toHaveCount(0);
});

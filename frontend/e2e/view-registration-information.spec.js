// SCRUM-36 View Registration Information
//   AC1  Event Organisers and Event Coordinators can view registration information
//        for events they are authorised to manage.
//   AC2  Registered attendee information is shown, such as name and contact details.
//   AC3  The total number of registered attendees is shown.
//   AC4  Each attendee's current registration status is shown.
//   AC5  Users cannot access registration information for events they do not manage.
import { test, expect } from '@playwright/test';
import { fixtures, signIn } from './helpers.js';

let data;
test.beforeAll(() => { data = fixtures(); });
// One confirmed place (the filler attendee) and one waitlisted (the Attendee).
const recordsPage = () => `/#/events/${data.waitlist.event_id}/registrations`;

async function expectRoster(page) {
  const section = page.getByRole('region', { name: 'Attendee registrations' });
  const table = section.getByRole('table', { name: 'Attendee registration records' });
  await expect(table).toBeVisible();
  await expect(section.locator('dt', { hasText: /^Confirmed$/ }).locator('+ dd')).toHaveText('1');
  await expect(section.locator('dt', { hasText: /^Waitlisted$/ }).locator('+ dd')).toHaveText('1');
  const confirmed = table.getByRole('row').filter({ hasText: 'Confirmed' });
  await expect(confirmed).toContainText(data.filler.name);
  await expect(confirmed).toContainText(data.filler.email);
  await expect(confirmed).toContainText(data.filler.phone);
  await expect(table.getByRole('row').filter({ hasText: 'Waitlisted' })).toHaveCount(1);
}

// E2E-REC-001 (AC1, AC2, AC3, AC4): the event's Organiser sees each attendee's name,
// contact details and status, and the totals.
test('the Organiser sees attendee details, statuses and totals', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto(recordsPage());
  await expectRoster(page);
});

// E2E-REC-002 (AC1): the event's Coordinator sees the same registration information.
test('the Coordinator sees the registration information', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  await page.goto(recordsPage());
  await expectRoster(page);
});

// E2E-REC-003 (AC5): an Organiser who does not manage the event sees no attendee details.
test('an Organiser of other events cannot see them', async ({ page }) => {
  await signIn(page, data.other_organiser);
  await page.goto(recordsPage());

  await expect(page.getByRole('region', { name: 'Attendee registrations' }).getByRole('alert')).toBeVisible();
  await expect(page.getByRole('table', { name: 'Attendee registration records' })).toHaveCount(0);
  await expect(page.getByText(data.filler.email)).toHaveCount(0);
});

// E2E-REC-004 (AC5): Venue Staff cannot open registration information.
test('Venue Staff cannot open registration information', async ({ page }) => {
  await signIn(page, 'Venue Staff');
  await page.goto(recordsPage());

  await expect(page).toHaveURL(/#\/home$/);
  await expect(page.getByText(data.filler.email)).toHaveCount(0);
});

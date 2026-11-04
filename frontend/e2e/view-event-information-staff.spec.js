// SCRUM-273 View Event Information to show relevant staff
//   AC1  The Event Information page displays the names and roles of the assigned Venue
//        Staff, Technical Support Staff, and Safety Officer for the selected event.
//
// The event is approved before the test, which assigns its staff. The page shows
// IDs from the event and looks the names up separately, falling back to the first
// 8 characters of each ID, so the test checks for each person's name.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { approvedEvent, nameOf, removeRequests, signIn, userId } from './helpers.js';

const name = `E2E event staff ${Date.now()}`;
const starts = DateTime.now().plus({ days: 190 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
// [label on the page, the role's test account, the events column]
const STAFF = [
  ['Venue staff', 'Venue Staff', 'venue_staff_id'],
  ['Technical support', 'Technical Support Staff', 'technical_support_id'],
  ['Safety officer', 'Safety Officer', 'safety_officer_id'],
];
let event;

test.beforeAll(async ({ request }) => {
  event = await approvedEvent(request, name, starts);
  // The expected names are the test accounts', so the approval must have picked them.
  for (const [, role, column] of STAFF) expect(event[column], `approval assigned another ${role}`).toBe(await userId(role));
});

test.afterAll(async () => {
  if (event) await removeRequests([event.event_request_id], name);
});

for (const [index, viewer] of ['Event Coordinator', 'Event Organiser'].entries()) {
  // E2E-VES-001 and E2E-VES-002 (AC1): the event's Coordinator and Organiser each open the
  // event and see every assigned staff member's name against their role.
  test(`E2E-VES-00${index + 1} the ${viewer} sees the assigned staff by name and role`, async ({ page }) => {
    await signIn(page, viewer);
    await page.goto(`/#/events/${event.event_id}`);

    const people = page.locator('section').filter({ has: page.getByRole('heading', { name: 'People' }) });
    for (const [label, role] of STAFF) {
      await expect(people.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('+ dd'))
        .toHaveText(await nameOf(role));
    }
  });
}

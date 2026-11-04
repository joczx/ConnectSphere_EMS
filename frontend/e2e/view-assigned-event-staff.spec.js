import { test, expect, admin, signIn } from './story-fixtures.js';

// SCRUM-273 AC1: stored staff IDs resolve to real names and roles on Event Information.
test('SCRUM-273: event page displays the assigned staff names and roles', async ({ page, story }) => {
  const event = await story.event();
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/events/${event.event_id}`);
  for (const [field, label] of [['venue_staff_id','Venue staff'], ['technical_support_id','Technical support'], ['safety_officer_id','Safety officer']]) {
    const [user] = await admin(`/rest/v1/users?user_id=eq.${event[field]}`);
    await expect(page.getByRole('main').getByText(label, { exact: true })).toBeVisible();
    await expect(page.getByRole('main')).toContainText(user.name);
  }
});

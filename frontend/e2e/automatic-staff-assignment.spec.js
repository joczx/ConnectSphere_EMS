import { test, expect, admin, signIn, waitForSave } from './story-fixtures.js';

// SCRUM-272: browser approval invokes real automatic staff assignment.
test('SCRUM-272: approved event records valid staff assignments without manual selection', async ({ page, story }) => {
  const row = await story.requestEvent(); await story.assign(row);
  await signIn(page, 'Event Coordinator'); await page.goto(`/#/review-event-requests/${row.event_request_id}`);
  await waitForSave(page, `/api/event-requests/${row.event_request_id}/review`, () => page.getByRole('button', { name: 'Approve', exact: true }).click());
  const [event] = await admin(`/rest/v1/events?event_request_id=eq.${row.event_request_id}`);
  for (const [field, role] of [['venue_staff_id','Venue Staff'], ['technical_support_id','Technical Support Staff'], ['safety_officer_id','Safety Officer']]) {
    expect(event[field]).toBeTruthy();
    const [roleRow] = await admin(`/rest/v1/roles?role_name=eq.${encodeURIComponent(role)}`);
    const assignments = await admin(`/rest/v1/user_roles?user_id=eq.${event[field]}&role_id=eq.${roleRow.role_id}`);
    expect(assignments).toHaveLength(1);
  }
  await page.goto(`/#/events/${event.event_id}`);
  await expect(page.getByRole('heading', { name: event.event_name, exact: true })).toBeVisible();
});

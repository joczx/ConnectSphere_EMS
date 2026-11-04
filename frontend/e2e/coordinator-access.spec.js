import { test, expect } from './story-fixtures.js';
import { admin, signIn, userId } from './helpers.js';

let event;

// An event in Planning that belongs to someone other than the Event Coordinator.
test.beforeAll(async () => {
  const organiser = await userId('Event Organiser');
  const owner = await userId('Event Coordinator Lead');
  const name = `E2E coordinator access ${Date.now()}`;
  const [request] = await admin('/rest/v1/event_request', { method: 'POST', body: {
    event_name: name, event_organiser_id: organiser, event_coordinator_id: owner, status: 'draft',
  } });
  const starts = new Date(Date.now() + 60 * 24 * 3600 * 1000);
  [event] = await admin('/rest/v1/events', { method: 'POST', body: {
    event_request_id: request.event_request_id, event_name: name,
    purpose: 'E2E test', description: 'Created by coordinator-access.spec.js; removed afterwards.',
    start_datetime: starts.toISOString(),
    end_datetime: new Date(starts.getTime() + 3 * 3600 * 1000).toISOString(),
    capacity_needed: 40, room_layout: 'theatre', required_facilities: [],
    equipment_requirements: [], safety_rework_arrangements: [],
    event_organiser_id: organiser, event_coordinator_id: owner, status: 'planning',
  } });
});

test.afterAll(async () => {
  if (!event) return;
  await admin(`/rest/v1/events?event_id=eq.${event.event_id}`, { method: 'DELETE' });
  await admin(`/rest/v1/event_request?event_request_id=eq.${event.event_request_id}`, { method: 'DELETE' });
});

// E2E-VCA-001 (SCRUM-218 AC3): another coordinator's event is not in the list.
test('coordinator does not see another coordinator\'s event', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  const loaded = page.waitForResponse(response => new URL(response.url()).pathname === '/api/events' && response.status() === 200);
  await page.goto('/#/events'); await loaded;
  await expect(page.getByRole('heading', { level: 1, name: 'Events', exact: true })).toBeVisible();
  await expect(page.getByText(event.event_name)).toHaveCount(0);
});

// E2E-VCA-002 (SCRUM-218 AC3): opening it by URL does not show its details.
test('coordinator cannot open it by URL', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  const loaded = page.waitForResponse(response => new URL(response.url()).pathname === `/api/events/${event.event_id}`);
  await page.goto(`/#/events/${event.event_id}`); await loaded;
  await expect(page.getByText(event.event_name)).toHaveCount(0);
});

// SCRUM-218 AC1/2: latest Lead workspace displays assigned active events.
test('SCRUM-218: Lead sees an active planning event and its coordinator', async ({ page, story }) => {
  const event = await story.event();
  await signIn(page, 'Event Coordinator Lead'); await page.goto('/#/reassign-event-coordinators');
  const card = page.locator('article').filter({ has: page.getByRole('heading', { name: event.event_name, exact: true }) });
  await expect(card).toBeVisible(); await expect(card).toContainText('Planning');
  const [coordinator] = await admin(`/rest/v1/users?user_id=eq.${event.event_coordinator_id}`);
  await expect(card).toContainText(coordinator.name);
});

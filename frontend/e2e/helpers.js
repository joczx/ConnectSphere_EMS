import { readFileSync } from 'node:fs';
import { expect } from '@playwright/test';
import { DateTime } from 'luxon';

export const account = role => {
  const key = 'INTEGRATION_' + role.toUpperCase().replaceAll(' ', '_');
  return { email: process.env[`${key}_EMAIL`], password: process.env[`${key}_PASSWORD`] };
};

// `who` is a role name, or an account from the fixtures ({ email, password }).
export async function signIn(page, who) {
  const { email, password } = typeof who === 'string' ? account(who) : who;
  // Sign out whoever a previous step signed in, or '/' skips straight to Home.
  await page.goto('/');
  await page.evaluate(() => sessionStorage.clear());
  await page.goto('/');
  await page.reload();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(/#\/home$/);
}

// Test data only: the secret key bypasses Row Level Security.
export async function admin(path, { method = 'GET', body } = {}) {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const response = await fetch(process.env.SUPABASE_URL + path, {
    method,
    body: body && JSON.stringify(body),
    headers: { apikey: key, Authorization: `Bearer ${key}`,
               'Content-Type': 'application/json', Prefer: 'return=representation' },
  });
  if (!response.ok) throw new Error(`${method} ${path}: ${response.status} ${await response.text()}`);
  const text = await response.text();
  return text ? JSON.parse(text) : [];
}

export async function userId(role) {
  const rows = await admin(`/rest/v1/users?select=user_id&email=eq.${encodeURIComponent(account(role).email)}`);
  return rows[0].user_id;
}

// The events and accounts global-setup.js created for this run.
export const FIXTURES_FILE = new URL('./.fixtures.json', import.meta.url);
export const fixtures = () => JSON.parse(readFileSync(FIXTURES_FILE, 'utf8'));

// Times as the pages show them.
export const registrationDate = value =>
  DateTime.fromISO(value).setZone('Asia/Singapore').toFormat('dd LLL yyyy, HH:mm') + ' SGT';
export const eventDate = value => new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
}).format(new Date(value));
// A value for a datetime-local input, in Singapore time.
export const inputTime = value => value.setZone('Asia/Singapore').toFormat("yyyy-MM-dd'T'HH:mm");

// The card for one event on the attendee Event registration page.
export const eventCard = (page, event) =>
  page.locator('article').filter({ has: page.getByRole('heading', { name: event.event_name }) });

// Calls the Flask API directly as `role`, for arranging a step a test is not about.
export async function apiAs(request, role, method, path, data) {
  const origin = process.env.E2E_API_ORIGIN || 'http://127.0.0.1:5000';
  const login = await request.post(origin + '/api/login', { data: account(role) });
  const { access_token: token } = await login.json();
  const response = await request.fetch(origin + path, {
    method, data, headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) throw new Error(`${method} ${path}: ${response.status()} ${await response.text()}`);
  return response.json();
}

// The display name of `role`'s test account, as notifications write it.
export async function nameOf(role) {
  const rows = await admin(`/rest/v1/users?select=name&email=eq.${encodeURIComponent(account(role).email)}`);
  return rows[0].name;
}

// A temporary account holding `role`, for when a test needs a second user in it.
// Returns { id, name, email, password }; remove it with deleteAccount().
export async function newAccount(name, role) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@connectsphere.invalid`;
  const password = `E2e-${Math.random().toString(36).slice(2)}`;
  const user = await admin('/auth/v1/admin/users', { method: 'POST', body: {
    email, password, email_confirm: true, user_metadata: { name },
  } });
  const [{ role_id: roleId }] = await admin(`/rest/v1/roles?select=role_id&role_name=eq.${encodeURIComponent(role)}`);
  await admin('/rest/v1/user_roles', { method: 'POST', body: { user_id: user.id, role_id: roleId } });
  return { id: user.id, name, email, password };
}

export const deleteAccount = who => admin(`/auth/v1/admin/users/${who.id}`, { method: 'DELETE' });

// Submits an event request as the Organiser, ready for a Lead to assign.
export async function submitRequest(request, name, starts) {
  const { event_request: row } = await apiAs(request, 'Event Organiser', 'POST', '/api/event-requests', {
    event_name: name, purpose: 'E2E test', description: `${name}: created by an e2e test.`,
    event_organiser_id: await userId('Event Organiser'),
    start_datetime: starts.toISO(), end_datetime: starts.plus({ hours: 3 }).toISO(), capacity_needed: 40,
    room_layout: 'theatre', required_facilities: ['projector'], equipment_requirements: [],
  });
  return row;
}

// Takes a request through assignment and approval to an event in Planning.
export async function approvedEvent(request, name, starts) {
  const row = await submitRequest(request, name, starts);
  await apiAs(request, 'Event Coordinator Lead', 'POST', `/api/event-requests/${row.event_request_id}/assign-coordinator`,
    { coordinator_id: await userId('Event Coordinator') });
  await apiAs(request, 'Event Coordinator', 'POST', `/api/event-requests/${row.event_request_id}/review`,
    { outcome: 'approved' });
  const [event] = await admin(`/rest/v1/events?select=*&event_request_id=eq.${row.event_request_id}`);
  return event;
}

// Removes event requests (and their events) and every notification about `name`.
export async function removeRequests(ids, name) {
  for (const id of ids) {
    await admin(`/rest/v1/events?event_request_id=eq.${id}`, { method: 'DELETE' });
    await admin(`/rest/v1/event_request?event_request_id=eq.${id}`, { method: 'DELETE' });
  }
  await admin(`/rest/v1/notifications?body=like.*${encodeURIComponent(name)}*`, { method: 'DELETE' });
}

// A catalogue item Technical Support can reserve. Remove it with removeEquipment().
export async function newEquipment(label) {
  const [row] = await admin('/rest/v1/equipment', { method: 'POST', body: {
    equipment_type: `E2E ${label} ${Date.now()}`, equipment_model: 'E2E', total_quantity: 10,
  } });
  return row;
}

// Removes an event's equipment requests and reservations, then the catalogue items.
// The secret key cannot delete an equipment request (guard_equipment_request_review()
// returns NULL for it), so each is reset to pending and deleted as the Coordinator.
export async function removeEquipment(request, event, items) {
  if (event) {
    await admin(`/rest/v1/equipment_reservations?event_id=eq.${event.event_id}`, { method: 'DELETE' });
    await admin(`/rest/v1/equipment_request?event_id=eq.${event.event_id}`, { method: 'PATCH', body: {
      status: 'pending', accepted_quantity: null, reviewed_by: null, reviewed_at: null,
      equipment_id: null, reason_for_rejection: null,
    } });
    const login = await request.post('http://127.0.0.1:5000/api/login', { data: account('Event Coordinator') });
    const { access_token: token } = await login.json();
    await fetch(`${process.env.SUPABASE_URL}/rest/v1/equipment_request?event_id=eq.${event.event_id}`, {
      method: 'DELETE', headers: { apikey: process.env.SUPABASE_ANON_KEY, Authorization: `Bearer ${token}` },
    });
  }
  for (const item of items.filter(Boolean)) {
    await admin(`/rest/v1/equipment?equipment_id=eq.${item.equipment_id}`, { method: 'DELETE' });
  }
}

// A venue that meets every test event's requirements. Remove it with removeVenues().
export async function newVenue(label) {
  const [row] = await admin('/rest/v1/venues', { method: 'POST', body: {
    venue_name: `E2E ${label} ${Date.now()}`, capacity: 100, postal_code: '123456', block_number: '1',
    street_name: 'E2E Street', wheelchair_accessible: false, blind_accessible: false,
    facilities: ['projector'], supported_room_layouts: ['theatre'],
    operating_hours: Object.fromEntries(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
      .map(day => [day, { open: '08:00', close: '22:00' }])),
    default_setup_minutes: 0, default_turnaround_minutes: 0,
  } });
  return row;
}

// Removes venues with their booking requests and unavailable periods.
export async function removeVenues(venues) {
  for (const venue of venues.filter(Boolean)) {
    for (const table of ['venue_booking_requests', 'venue_blocks', 'venues']) {
      await admin(`/rest/v1/${table}?venue_id=eq.${venue.venue_id}`, { method: 'DELETE' });
    }
  }
}

// The Coordinator requests `venue` for `event`; returns the booking request.
export async function bookVenue(request, event, venue) {
  const { booking } = await apiAs(request, 'Event Coordinator', 'POST', '/api/venue-bookings', {
    event_id: event.event_id, venue_id: venue.venue_id, event_name: event.event_name, attendance: 40,
    venue_requirements: 'E2E test', starts_at: event.start_datetime, ends_at: event.end_datetime,
  });
  return booking;
}

// A time as notifications write it: '05 Jan 2027 10:00' (Singapore time).
export const notifiedTime = value =>
  (typeof value === 'string' ? DateTime.fromISO(value) : value).setZone('Asia/Singapore').toFormat('dd LLL yyyy HH:mm');

// The single notification on the signed-in user's Notifications page with this
// title that mentions every one of `texts`.
export async function notification(page, title, ...texts) {
  await page.goto('/#/notifications');
  // The title must match exactly: hasText ignores case, so "Venue unavailable" would
  // otherwise match any notification about an event named "E2E venue unavailable".
  let item = page.getByRole('main').getByRole('listitem')
    .filter({ has: page.getByText(title, { exact: true }) });
  for (const text of texts) item = item.filter({ hasText: text });
  await expect(item).toHaveCount(1);
  return item;
}

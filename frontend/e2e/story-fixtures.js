// Shared arrangements only: the action/assertion under test stays in each spec.
import { test as base, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { DateTime } from 'luxon';
import { account, admin, inputTime, signIn, userId } from './helpers.js';
export { expect, admin, signIn, inputTime, userId };
const tokens = new Map();
const apiOrigin = process.env.E2E_API_ORIGIN || 'http://127.0.0.1:5000';

export class StoryData {
  constructor(request, info) {
    this.request = request;
    this.prefix = `E2E-story-${randomUUID().slice(0, 10)}`;
    this.requests = new Set(); this.venues = new Set(); this.equipment = new Set(); this.users = new Set();
    this.info = info;
  }
  async token(who) {
    if (typeof who !== 'string') return who.token;
    if (!tokens.has(who)) {
      const credentials = account(who);
      expect(credentials.email, `Configure integration credentials for ${who}`).toBeTruthy();
      const response = await this.request.post(apiOrigin + '/api/login', { data: credentials });
      expect(response.status(), `Sign in as ${who}`).toBe(200);
      tokens.set(who, (await response.json()).access_token);
    }
    return tokens.get(who);
  }
  async call(who, method, path, data, expected = 200) {
    const response = await this.request.fetch(apiOrigin + path, {
      method, data, headers: { Authorization: `Bearer ${await this.token(who)}` },
    });
    expect(response.status(), `${method} ${path}`).toBe(expected);
    return response.json();
  }
  async requestEvent({ draft = false, ...changes } = {}) {
    const start = DateTime.now().setZone('Asia/Singapore').plus({ days: 100 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
    const payload = { event_name: this.prefix, purpose: 'E2E acceptance test', description: this.prefix + ' description',
      event_organiser_id: await userId('Event Organiser'), start_datetime: start.toISO(), end_datetime: start.plus({ hours: 3 }).toISO(),
      capacity_needed: 40, room_layout: 'theatre', required_facilities: ['projector'], equipment_requirements: [], save_as_draft: draft, ...changes };
    const result = await this.call('Event Organiser', 'POST', '/api/event-requests', payload, 201);
    this.requests.add(result.event_request.event_request_id);
    return result.event_request;
  }
  async assign(row, who) {
    who ||= await userId('Event Coordinator');
    return this.call('Event Coordinator Lead', 'POST', `/api/event-requests/${row.event_request_id}/assign-coordinator`, { coordinator_id: who });
  }
  async review(row, outcome = 'approved', comments = '') {
    return this.call('Event Coordinator', 'POST', `/api/event-requests/${row.event_request_id}/review`, { outcome, comments });
  }
  async event(changes = {}) {
    const row = await this.requestEvent(changes);
    await this.assign(row); await this.review(row);
    return (await admin(`/rest/v1/events?event_request_id=eq.${row.event_request_id}`))[0];
  }
  async venue(changes = {}) {
    const [row] = await admin('/rest/v1/venues', { method: 'POST', body: {
      venue_name: this.prefix + ' Hall ' + this.venues.size, capacity: 200, postal_code: '123456', block_number: '1', street_name: 'E2E Street',
      wheelchair_accessible: true, blind_accessible: true, facilities: ['projector'], supported_room_layouts: ['theatre'],
      default_setup_minutes: 0, default_turnaround_minutes: 0,
      operating_hours: Object.fromEntries(['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].map(day => [day, { open: '00:00', close: '23:59' }])), ...changes,
    } });
    this.venues.add(row.venue_id); return row;
  }
  async book(event, venue, approved = false) {
    const { booking } = await this.call('Event Coordinator', 'POST', '/api/venue-bookings', {
      event_id: event.event_id, venue_id: venue.venue_id, event_name: event.event_name,
      attendance: event.capacity_needed, starts_at: event.start_datetime, ends_at: event.end_datetime, venue_requirements: this.prefix,
    }, 201);
    if (approved) await this.call('Venue Staff', 'POST', `/api/venue-bookings/${booking.booking_id}/review`, { outcome: 'approved' });
    return booking;
  }
  async safety() {
    const event = await this.event(); const venue = await this.venue();
    const booking = await this.book(event, venue, true);
    await this.call('Event Coordinator', 'POST', `/api/events/${event.event_id}/safety-checks`);
    return { event, venue, booking };
  }
  async item() {
    const [item] = await admin('/rest/v1/equipment', { method: 'POST', body: {
      equipment_type: this.prefix + ' Projector', equipment_model: 'HDMI', total_quantity: 10,
    } });
    this.equipment.add(item.equipment_id); return item;
  }
  async equipmentRequest(event, item, quantity = 2) {
    return (await this.call('Event Coordinator', 'POST', `/api/events/${event.event_id}/equipment-requests`, {
      equipment_type: item.equipment_type, quantity, technical_requirements: this.prefix + ' HDMI setup',
    }, 201)).equipment_request;
  }
  async reservation(row, item, quantity = 2) {
    return this.call('Technical Support Staff', 'POST', `/api/equipment-request-reviews/${row.equipment_request_id}/reservation`, {
      equipment_id: item.equipment_id, quantity,
    }, 201);
  }
  async change(event, values = { capacity_needed: 41 }) {
    const [current] = await admin(`/rest/v1/events?event_id=eq.${event.event_id}`);
    return (await this.call('Event Organiser', 'POST', `/api/events/${event.event_id}/change-requests`, {
      reason: this.prefix + ' updated requirements', proposed_values: values, expected_event_updated_at: current.updated_at,
    }, 201)).change_request;
  }
  async temporaryUser(role) {
    const email = this.prefix + '@connectsphere.invalid', password = randomUUID();
    const user = await admin('/auth/v1/admin/users', { method: 'POST', body: { email, password, email_confirm: true, user_metadata: { name: this.prefix } } });
    this.users.add(user.id);
    const [assigned] = await admin(`/rest/v1/roles?role_name=eq.${encodeURIComponent(role)}`);
    await admin('/rest/v1/user_roles', { method: 'POST', body: { user_id: user.id, role_id: assigned.role_id } });
    const response = await this.request.post(apiOrigin + '/api/login', { data: { email, password } });
    expect(response.status()).toBe(200);
    return { id: user.id, email, password, token: (await response.json()).access_token };
  }
  async trackBrowserRequest(page, action) {
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/event-requests' && r.request().method() === 'POST');
    response.catch(() => {}); // The original action error still fails the test if it cannot submit.
    await action(); const saved = await response; const body = await saved.json();
    if (body.event_request?.event_request_id) this.requests.add(body.event_request.event_request_id);
    expect(saved.status()).toBe(201); return body.event_request;
  }
  async confirmed({ capacity = 40, waitingList = false } = {}) {
    const event = await this.event({ capacity_needed: capacity }); const venue = await this.venue();
    await this.book(event, venue, true);
    await this.call('Event Coordinator', 'POST', `/api/events/${event.event_id}/safety-checks`);
    await this.call('Safety Officer', 'POST', `/api/operational-safety-reviews/${event.event_id}/decision`, { outcome: 'approved' });
    await this.call('Event Organiser', 'PATCH', `/api/events/${event.event_id}/registration-period`, {
      registration_opens_at: DateTime.now().minus({ days: 1 }).toISO(), registration_closes_at: DateTime.now().plus({ days: 5 }).toISO(), waiting_list_enabled: waitingList,
    });
    return { event, venue };
  }
  async close() {
    const errors = [];
    const attempt = async fn => { try { await fn(); } catch (e) { errors.push(e.message); } };
    for (const id of this.requests) {
      for (const event of await admin(`/rest/v1/events?event_request_id=eq.${id}`)) {
        const q = `?event_id=eq.${event.event_id}`;
        await attempt(() => admin('/rest/v1/equipment_reservations' + q, { method: 'DELETE' }));
        const equipmentRows = await admin('/rest/v1/equipment_request' + q);
        if (equipmentRows.length) {
          await attempt(() => admin('/rest/v1/equipment_request' + q, { method: 'PATCH', body: {
            status: 'pending', accepted_quantity: null, reviewed_by: null, reviewed_at: null, equipment_id: null, reason_for_rejection: null,
          } }));
          for (const row of equipmentRows) await attempt(() => this.call('Event Coordinator', 'DELETE', `/api/events/${event.event_id}/equipment-requests/${row.equipment_request_id}`));
        }
        for (const table of ['event_registration', 'venue_booking_requests', 'events']) {
          await attempt(() => admin('/rest/v1/' + table + q, { method: 'DELETE' }));
        }
      }
      await attempt(() => admin(`/rest/v1/event_request?event_request_id=eq.${id}`, { method: 'DELETE' }));
    }
    for (const id of this.venues) {
      for (const table of ['venue_blocks', 'venues']) await attempt(() => admin(`/rest/v1/${table}?venue_id=eq.${id}`, { method: 'DELETE' }));
    }
    for (const id of this.equipment) await attempt(() => admin(`/rest/v1/equipment?equipment_id=eq.${id}`, { method: 'DELETE' }));
    await attempt(() => admin(`/rest/v1/notifications?body=like.*${this.prefix}*`, { method: 'DELETE' }));
    for (const id of this.users) await attempt(() => admin(`/auth/v1/admin/users/${id}`, { method: 'DELETE' }));
    expect(errors, 'Clean up only this test\'s uniquely named fixtures').toEqual([]);
  }
}

export const test = base.extend({
  story: async ({ request }, use, info) => {
    info.setTimeout(Math.max(info.timeout, 90_000));
    const data = new StoryData(request, info);
    try { await use(data); } finally { await data.close(); }
  },
});

export async function fillRequest(page, name) {
  const start = DateTime.now().plus({ days: 100 }).set({ hour: 10, minute: 0, second: 0, millisecond: 0 });
  for (const [label, value] of [['Event name', name], ['Purpose', 'Community learning'], ['Description', name + ' description'],
    ['Start date and time', inputTime(start)], ['End date and time', inputTime(start.plus({ hours: 3 }))], ['Expected attendance', '40']]) await page.getByLabel(label).fill(value);
  await page.getByLabel('Room layout').selectOption('theatre');
  await page.getByLabel('No facilities needed').check();
  await page.getByLabel('No equipment needed').check();
}
export async function notifications(page, role, eventName, title) {
  await signIn(page, role); await page.goto('/#/notifications');
  const row = page.getByRole('main').getByRole('listitem').filter({ hasText: eventName }).filter({ hasText: title });
  await expect(row).toHaveCount(1); return row;
}
export async function waitForSave(page, path, action) {
  const pending = page.waitForResponse(r => new URL(r.url()).pathname === path && ['POST','PATCH','DELETE'].includes(r.request().method()));
  pending.catch(() => {}); // Avoid an orphan rejection when the UI action itself fails.
  const nativeDialog = dialog => dialog.accept();
  page.on('dialog', nativeDialog);
  try {
    await action();
    const dialog = page.getByRole('dialog');
    if (await dialog.isVisible()) await dialog.getByRole('button').last().click();
  } finally { page.off('dialog', nativeDialog); }
  const response = await pending;
  expect(response.ok(), `Browser mutation ${path}`).toBeTruthy(); return response.json();
}

export async function fillVenue(page, name) {
  for (const [label, value] of [['Venue name', name], ['Capacity', '200'], ['Postal code', '123456'], ['Block number', '1'], ['Street name', 'E2E Street'],
    ['Default setup time (minutes)', '0'], ['Default turnaround time (minutes)', '0']]) await page.getByLabel(label).fill(value);
  await page.getByLabel('Projector').check();
  await page.getByLabel('Theatre').check();
  for (const day of ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']) {
    await page.getByLabel(day + ' opening time', { exact: true }).fill('08:00');
    await page.getByLabel(day + ' closing time', { exact: true }).fill('22:00');
  }
}

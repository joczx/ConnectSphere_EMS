import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';
import { hasAccess, rolesForPath } from '../src/auth/access.js';

test('home gives attendees personal registrations and organisers their own planning dashboard', async () => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = { window: globalThis.window, document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT, auth: globalThis.__attendeeDashboardAuth };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const paths = [];
  let refuseWithdrawal = true;
  let records = ['registered', 'waiting_list', 'withdrawn'].map((status, index) => ({
    event_id: index + 1, event_name: `My event ${index + 1}`, status,
    start_datetime: '2027-01-10T02:00:00Z', end_datetime: '2027-01-10T04:00:00Z', venues: ['Conference Hall'],
  }));
  globalThis.__attendeeDashboardAuth = {
    canAccess: path => hasAccess(['Attendee'], rolesForPath(path)),
    session: { user: { email: 'attendee@example.com' } }, signOut() {},
    account: { user: { roles: ['Attendee'], email: 'attendee@example.com' } }, accountReady: true,
    api: async (path, options) => {
      paths.push(path);
      if (path.endsWith('/registrations/withdraw')) {
        assert.equal(path, '/api/events/1/registrations/withdraw');
        assert.equal(options.method, 'POST');
        assert.deepEqual(options.body, {});
        if (refuseWithdrawal) throw new Error('Registration cannot be withdrawn at or after the event start time.');
        records = records.map(item => item.event_id === 1 ? { ...item, status: 'withdrawn' } : item);
        return { registration: { status: 'withdrawn', withdrawn_at: new Date().toISOString() },
          available_capacity: 1, message: 'Your registration has been successfully withdrawn.' };
      }
      assert.equal(path, '/api/my-registrations');
      return { registrations: records };
    },
  };
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    plugins: [{ name: 'dashboard-test-auth', enforce: 'pre',
      resolveId(id) { if (id.endsWith('/auth/AuthContext')) return '\0dashboard-test-auth'; },
      load(id) { if (id === '\0dashboard-test-auth') return 'export const useAuth = () => globalThis.__attendeeDashboardAuth;'; },
    }],
  });
  let root;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { MemoryRouter } = await import('react-router-dom');
    const { default: Home } = await server.ssrLoadModule('/src/pages/Home.jsx');
    const { FeedbackProvider } = await server.ssrLoadModule('/src/components/FeedbackProvider.jsx');
    root = createRoot(document.getElementById('root'));
    await act(async () => root.render(h(MemoryRouter, null, h(FeedbackProvider, null, h(Home)))));
    const text = document.body.textContent;
    for (const expected of ['My event 1', 'My event 2', 'My event 3', 'Confirmed', 'Waitlisted', 'Withdrawn', 'Conference Hall']) {
      assert.ok(text.includes(expected), expected);
    }
    for (const excluded of ['Needs attention', 'Upcoming events', 'Events visible to your account', 'equipment requests are accepted']) {
      assert.ok(!text.includes(excluded), excluded);
    }
    assert.equal(document.querySelector('a[href="/events"]'), null);
    assert.deepEqual(paths, ['/api/my-registrations']);
    const card = () => [...document.querySelectorAll('article')].find(item => item.textContent.includes('My event 1'));
    const withdraw = () => card().querySelector('button');
    assert.equal(withdraw().disabled, false);
    await act(async () => withdraw().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    assert.ok(card().textContent.includes('Registration status: Confirmed'), 'server refusal preserves status');
    assert.ok(card().querySelector('[role="alert"]').textContent.includes('at or after the event start'));
    refuseWithdrawal = false;
    await act(async () => withdraw().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    assert.ok(card().textContent.includes('Registration status: Withdrawn'));
    assert.equal(card().querySelector('button'), null);
    assert.ok(document.body.textContent.includes('Your registration has been successfully withdrawn.'));
    records = records.map(item => ({ ...item, start_datetime: '2000-01-01T00:00:00Z' }));
    const refreshBeforeStartCheck = [...document.querySelectorAll('button')].find(button => button.textContent === 'Refresh');
    await act(async () => refreshBeforeStartCheck.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    const waitlistedCard = [...document.querySelectorAll('article')].find(item => item.textContent.includes('My event 2'));
    assert.equal(waitlistedCard.querySelector('button').disabled, true, 'started events cannot be withdrawn');
    records = [];
    const refresh = [...document.querySelectorAll('button')].find(button => button.textContent === 'Refresh');
    await act(async () => refresh.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    assert.ok(document.body.textContent.includes('You have no registration records.'));
    assert.ok(!document.body.textContent.includes('My event 1'));
    globalThis.__attendeeDashboardAuth.canAccess = path => hasAccess(['Event Organiser'], rolesForPath(path));
    globalThis.__attendeeDashboardAuth.userId = 'me';
    globalThis.__attendeeDashboardAuth.account = { user: { roles: ['Event Organiser'] } };
    globalThis.__attendeeDashboardAuth.api = async path => {
      if (path === '/api/events/status-refresh') return {};
      if (path === '/api/events') return { events: [{ event_id: 1, event_organiser_id: 'me', event_name: 'Organiser conference',
        status: 'confirmed', start_datetime: new Date(Date.now() + 7 * 86400000).toISOString() }] };
      if (path.startsWith('/api/event-requests?')) return { event_requests: [{ event_request_id: 8, event_organiser_id: 'me', status: 'draft', event_name: 'Draft conference' }] };
      if (path === '/api/notifications?limit=5') return { items: [{ notification_id: 1, title: 'Request approved', body: 'Your event can proceed.' }] };
      if (path === '/api/events/1/registrations') return { total_registered: 2, total_waitlisted: 1, total_withdrawn: 1 };
      if (path === '/api/venue-bookings/events/1') return { bookings: [{ status: 'approved', venue_name: 'Approved Hall' }] };
      throw new Error('Unexpected organiser query: ' + path);
    };
    await act(async () => root.render(h(MemoryRouter, null, h(FeedbackProvider, null, h(Home)))));
    assert.ok(document.querySelector('[aria-label="Event organiser dashboard"]'));
    assert.equal(document.querySelectorAll('.organiser-status-card').length, 8);
    for (const expected of ['Draft conference', 'Organiser conference', 'Approved Hall', 'Registration summary', 'Request approved', 'Set registration dates']) {
      assert.ok(document.body.textContent.includes(expected), expected);
    }
    assert.ok(!document.body.textContent.includes('Events visible to your account'));
    assert.ok(!document.body.textContent.includes('No pending work in the loaded queues.'));
    assert.ok(document.querySelector('a[href="/event-requests/new"]'));
    assert.ok(document.querySelector('a[href="/events"]'));
  } finally {
    if (root) { const { act } = await import('react'); await act(async () => root.unmount()); }
    await server.close();
    dom.window.close();
    globalThis.window = previous.window;
    globalThis.document = previous.document;
    globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
    globalThis.__attendeeDashboardAuth = previous.auth;
  }
});

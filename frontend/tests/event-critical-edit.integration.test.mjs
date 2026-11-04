// Component integration tests for the critical-event-edit confirmation flow.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';


const coordinatorId = '11111111-1111-4111-8111-111111111111';
const token = `x.${Buffer.from(JSON.stringify({ sub: coordinatorId })).toString('base64url')}.x`;

const originalEvent = {
  event_id: 42,
  event_request_id: 24,
  event_name: 'Integration planning event',
  purpose: 'Exercise the critical edit flow',
  description: 'A planning event with existing arrangements.',
  start_datetime: '2027-02-10T02:00:00+00:00',
  end_datetime: '2027-02-10T05:00:00+00:00',
  capacity_needed: 40,
  room_layout: 'theatre',
  required_facilities: ['projector'],
  need_wheelchair_accessibility: false,
  need_blind_accessibility: false,
  equipment_requirements: [],
  event_organiser_id: '22222222-2222-4222-8222-222222222222',
  event_coordinator_id: coordinatorId,
  technical_support_id: null,
  venue_staff_id: null,
  safety_officer_id: null,
  venue_id: null,
  status: 'planning',
  updated_at: '2026-11-04T00:00:00+00:00',
};

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

async function exerciseCriticalEdit(choice) {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/events/42' });
  const originals = {
    window: globalThis.window,
    document: globalThis.document,
    sessionStorage: globalThis.sessionStorage,
    fetch: globalThis.fetch,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT,
  };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.sessionStorage = dom.window.sessionStorage;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  dom.window.HTMLDialogElement.prototype.close = function () { this.open = false; };
  sessionStorage.setItem('auth_session', JSON.stringify({ access_token: token }));

  const patchBodies = [];
  let savedEvent = { ...originalEvent };
  globalThis.fetch = async (url, options = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    if (url === '/api/users/me') return json({ user: { user_id: coordinatorId, roles: ['Event Coordinator'] } });
    if (url === '/api/events/status-refresh') return json({});
    if (url === '/api/events/42' && method === 'GET') return json({ event: savedEvent });
    if (url === '/api/events/42' && method === 'PATCH') {
      const body = JSON.parse(options.body);
      patchBodies.push(body);
      if (!body.confirm_critical) {
        return json({ error: 'Confirm critical changes.', critical_fields: ['Expected attendance'] }, 409);
      }
      savedEvent = { ...savedEvent, capacity_needed: body.capacity_needed, updated_at: '2026-11-04T00:01:00+00:00' };
      return json({ message: 'Event information updated successfully.', event: savedEvent });
    }
    if (url === '/api/events/42/equipment-requests') return json({ equipment_requests: [] });
    if (url === '/api/events/42/activity') return json({ activity: [] });
    if (url === '/api/venue-bookings/events/42') return json({ bookings: [] });
    if (url.startsWith('/api/users?ids=')) return json({ users: {} });
    if (url === '/api/events/42/registrations') return json({ registrations: [] });
    if (url.startsWith('/api/notifications')) return json({ items: [], unread: 0 });
    return json({});
  };

  const server = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  let root;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { MemoryRouter, Route, Routes } = await import('react-router-dom');
    const { FeedbackProvider } = await server.ssrLoadModule('/src/components/FeedbackProvider.jsx');
    const { AuthProvider } = await server.ssrLoadModule('/src/auth/AuthContext.jsx');
    const { default: Events } = await server.ssrLoadModule('/src/pages/Events.jsx');

    root = createRoot(document.getElementById('root'));
    await act(async () => root.render(
      h(FeedbackProvider, null,
        h(AuthProvider, null,
          h(MemoryRouter, { initialEntries: ['/events/42'] },
            h(Routes, null, h(Route, { path: '/events/:eventId', element: h(Events) }))))),
    ));

    const flush = async () => {
      for (let index = 0; index < 4; index += 1) {
        await act(async () => new Promise(resolve => setTimeout(resolve, 0)));
      }
    };
    const click = async text => {
      const button = [...document.querySelectorAll('button')].find(node => node.textContent === text);
      assert.ok(button, `button ${text} exists`);
      await act(async () => button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
      await flush();
    };

    await flush();
    await click('Edit event');
    const capacity = [...document.querySelectorAll('label')]
      .find(label => label.textContent.startsWith('Expected attendance'))?.querySelector('input');
    assert.ok(capacity, 'expected-attendance input exists');
    const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set;
    await act(async () => {
      setter.call(capacity, '55');
      capacity.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      capacity.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });
    await click('Save changes');

    const dialog = document.querySelector('dialog');
    assert.ok(dialog?.open, 'critical-change confirmation opens');
    assert.match(dialog.textContent, /Expected attendance/);
    assert.match(dialog.textContent, /existing venue bookings and equipment reservations/);
    await click(choice);

    return { patchBodies, text: document.body.textContent };
  } finally {
    if (root) {
      const { act } = await import('react');
      await act(async () => root.unmount());
    }
    await server.close();
    dom.window.close();
    globalThis.window = originals.window;
    globalThis.document = originals.document;
    globalThis.sessionStorage = originals.sessionStorage;
    globalThis.fetch = originals.fetch;
    globalThis.IS_REACT_ACT_ENVIRONMENT = originals.act;
  }
}


test('confirming a critical event edit retries it with explicit confirmation', async () => {
  const result = await exerciseCriticalEdit('Confirm and save');

  assert.equal(result.patchBodies.length, 2);
  assert.equal(result.patchBodies[0].capacity_needed, 55);
  assert.equal(result.patchBodies[0].confirm_critical, undefined);
  assert.equal(result.patchBodies[1].capacity_needed, 55);
  assert.equal(result.patchBodies[1].confirm_critical, true);
  assert.match(result.text, /Event information updated successfully/);
});


test('discarding a critical event edit leaves the saved event unchanged', async () => {
  const result = await exerciseCriticalEdit('Discard changes');

  assert.equal(result.patchBodies.length, 1);
  assert.equal(result.patchBodies[0].capacity_needed, 55);
  assert.match(result.text, /Your unsaved event changes have been discarded/);
  assert.doesNotMatch(result.text, /Save changes/);
});

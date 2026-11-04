import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';

test('successful registration and waiting list are confirmed by the on-screen alert', async () => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = { window: globalThis.window, document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT, auth: globalThis.__registrationAlertAuth };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  let state, confirmation, submitted = false;
  const now = Date.now();
  const iso = offset => new Date(now + offset).toISOString();
  const event = { event_id: 41, event_name: 'Technology Fair', status: 'confirmed',
    start_datetime: iso(86400000), end_datetime: iso(172800000),
    registration_opens_at: iso(-86400000), registration_closes_at: iso(43200000) };
  globalThis.__registrationAlertAuth = { api: async (path, options) => {
    if (path === '/api/registration-events') return { events: [{ ...event, my_registration: submitted ? state : null }] };
    assert.equal(path, '/api/events/41/registrations');
    assert.equal(options.method, 'POST');
    assert.equal(options.successFeedback, false);
    assert.deepEqual(options.body, { full_name: 'Alex Tan', contact_email: 'alex@example.com', contact_phone: '+65 8123 4567' });
    submitted = true;
    return { registration: { status: state }, message: confirmation };
  } };
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    plugins: [{ name: 'registration-alert-test', enforce: 'pre',
      resolveId(id) {
        if (id.endsWith('/auth/AuthContext')) return '\0registration-alert-auth';
        if (id.endsWith('/components/Navbar') || id.endsWith('/components/WithdrawRegistration')) return '\0registration-alert-stub';
      },
      load(id) {
        if (id === '\0registration-alert-auth') return 'export const useAuth = () => globalThis.__registrationAlertAuth;';
        if (id === '\0registration-alert-stub') return 'export default function Stub() { return null; }';
      },
    }],
  });
  let root;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { MemoryRouter } = await import('react-router-dom');
    const { default: AttendeeEvents } = await server.ssrLoadModule('/src/pages/AttendeeEvents.jsx');
    root = createRoot(document.getElementById('root'));
    for (const [status, message] of [
      ['registered', 'You are registered for the event.'],
      ['waiting_list', 'You have joined the waiting list. Your place is not confirmed.'],
    ]) {
      state = status; confirmation = message; submitted = false;
      await act(async () => root.render(h(MemoryRouter, null, h(AttendeeEvents, { key: status }))));
      const register = [...document.querySelectorAll('button')].find(button => button.textContent === 'Register');
      await act(async () => register.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
      for (const [name, value] of Object.entries({ full_name: 'Alex Tan', contact_email: 'alex@example.com', contact_phone: '+65 8123 4567' })) {
        await act(async () => {
          const input = document.querySelector(`input[name="${name}"]`);
          Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, value);
          input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
        });
      }
      await act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })));
      assert.equal(submitted, true);
      assert.ok(document.querySelector('main [role="alert"]').textContent.includes(message));
      assert.equal(document.querySelector('form'), null);
    }
  } finally {
    if (root) { const { act } = await import('react'); await act(async () => root.unmount()); }
    await server.close();
    dom.window.close();
    globalThis.window = previous.window;
    globalThis.document = previous.document;
    globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
    globalThis.__registrationAlertAuth = previous.auth;
  }
});

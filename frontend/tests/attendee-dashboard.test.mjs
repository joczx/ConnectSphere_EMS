import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';
import { hasAccess, rolesForPath } from '../src/auth/access.js';

test('attendee dashboard shows personal registrations without staff queues or event API calls', async () => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = { window: globalThis.window, document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT, auth: globalThis.__attendeeDashboardAuth };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const paths = [];
  let records = ['registered', 'waiting_list', 'withdrawn'].map((status, index) => ({
    event_id: index + 1, event_name: `My event ${index + 1}`, status,
    start_datetime: '2027-01-10T02:00:00Z', end_datetime: '2027-01-10T04:00:00Z', venues: ['Conference Hall'],
  }));
  globalThis.__attendeeDashboardAuth = {
    canAccess: path => hasAccess(['Attendee'], rolesForPath(path)),
    session: { user: { email: 'attendee@example.com' } }, signOut() {},
    account: { user: { roles: ['Attendee'], email: 'attendee@example.com' } }, accountReady: true,
    api: async path => {
      paths.push(path);
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
    records = [];
    const refresh = [...document.querySelectorAll('button')].find(button => button.textContent === 'Refresh');
    await act(async () => refresh.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    assert.ok(document.body.textContent.includes('You have no registration records.'));
    assert.ok(!document.body.textContent.includes('My event 1'));
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

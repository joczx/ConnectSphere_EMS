import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';

test('event summary shows counts/link, record view shows details and access errors remove stale details', async () => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = { window: globalThis.window, document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT, auth: globalThis.__rosterViewAuth };
  globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.__rosterViewAuth = { api: async path => {
    if (path === '/api/events/25/registrations') throw new Error('Event not found or access unavailable.');
    return { event: { event_id: 24, event_name: 'Conference' }, total_registered: 2, total_waitlisted: 1, total_withdrawn: 1,
      registrations: [{ attendee_id: 'one', full_name: 'Alex Tan', contact_email: 'alex@example.com',
        contact_phone: '81234567', status: 'registered', registered_at: '2026-10-30T02:00:00Z' }] };
  } };
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    plugins: [{ name: 'roster-view-test-auth', enforce: 'pre',
      resolveId(id) { if (id.endsWith('/auth/AuthContext')) return '\0roster-view-auth'; },
      load(id) { if (id === '\0roster-view-auth') return 'export const useAuth = () => globalThis.__rosterViewAuth;'; },
    }],
  });
  let root;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { MemoryRouter } = await import('react-router-dom');
    const { default: Roster } = await server.ssrLoadModule('/src/components/EventRegistrationRoster.jsx');
    root = createRoot(document.getElementById('root'));
    const render = async props => act(async () => root.render(h(MemoryRouter, null, h(Roster, props))));
    await render({ eventId: 24, summaryOnly: true });
    assert.deepEqual([...document.querySelectorAll('dd')].map(item => item.textContent), ['2', '1', '1']);
    assert.equal(document.querySelector('table'), null);
    assert.ok(!document.body.textContent.includes('alex@example.com'));
    assert.equal(document.querySelector('a').getAttribute('href'), '/events/24/registrations');
    assert.equal(document.querySelector('a').textContent, 'View registration records');
    await render({ eventId: 24 });
    assert.ok(document.querySelector('table').textContent.includes('Alex Tan'));
    assert.ok(document.querySelector('table').textContent.includes('alex@example.com'));
    assert.ok(document.querySelector('table').textContent.includes('81234567'));
    assert.ok(document.querySelector('table').textContent.includes('Confirmed'));
    await render({ eventId: 25 });
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('access unavailable'));
    assert.equal(document.querySelector('table'), null);
    assert.ok(!document.body.textContent.includes('alex@example.com'));
  } finally {
    if (root) { const { act } = await import('react'); await act(async () => root.unmount()); }
    await server.close(); dom.window.close();
    globalThis.window = previous.window; globalThis.document = previous.document;
    globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act; globalThis.__rosterViewAuth = previous.auth;
  }
});

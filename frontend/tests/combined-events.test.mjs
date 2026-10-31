import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';

test('combined events retain zero-count status filters and request links/actions', async () => {
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    plugins: [{ name: 'combined-events-test-context', enforce: 'pre',
      resolveId(id) {
        if (id.endsWith('/auth/AuthContext')) return '\0combined-auth';
        if (id.endsWith('/FeedbackProvider')) return '\0combined-feedback';
      },
      load(id) {
        if (id === '\0combined-auth') return 'export const useAuth = () => ({api: async () => ({}), can: () => true});';
        if (id === '\0combined-feedback') return 'export const useFeedback = () => ({confirm: async () => false});';
      },
    }],
  });
  try {
    const { createElement: h } = await import('react');
    const { renderToString } = await import('react-dom/server');
    const { StaticRouter } = await import('react-router-dom');
    const { default: EventList } = await server.ssrLoadModule('/src/components/EventList.jsx');
    const { HOME_APPS } = await server.ssrLoadModule('/src/config/apps.js');
    assert.ok(!HOME_APPS.some(app => app.id === 'event-requests'));
    const render = events => new jsdom.JSDOM(renderToString(h(StaticRouter, { location: '/events' }, h(EventList, { events, onRequestChanged() {} }))));
    const empty = render([]);
    const labels = [...empty.window.document.querySelectorAll('.events-status-pills button')].map(button => button.textContent);
    assert.deepEqual(labels, ['All 0', 'Draft 0', 'Submitted 0', 'Planning 0', 'Pending safety checks 0', 'Confirmed 0', 'Completed 0', 'Rejected 0', 'Cancelled 0']);
    empty.window.close();
    const filled = render([
      { event_request_id: 1, workspace_type: 'request', workspace_key: 'request-1', workspace_path: '/event-requests/1', event_name: 'Draft workshop', status: 'draft' },
      { event_request_id: 2, workspace_type: 'request', workspace_key: 'request-2', workspace_path: '/event-requests/2', event_name: 'Rejected workshop', status: 'rejected' },
      { event_id: 3, event_name: 'Confirmed workshop', status: 'confirmed' },
    ]);
    const document = filled.window.document;
    assert.ok(document.querySelector('a[href="/event-requests/1"]').textContent.includes('Continue editing draft'));
    assert.ok(document.querySelector('a[href="/event-requests/2"]').textContent.includes('Amend and resubmit'));
    assert.ok(document.querySelector('a[href="/events/3"]'));
    assert.ok(document.querySelector('[aria-label="Delete draft Draft workshop"]'));
    assert.equal([...document.querySelectorAll('button')].filter(button => button.textContent === 'Cancel request').length, 2);
    assert.equal(document.querySelector('a button'), null);
    const buttons = [...document.querySelectorAll('.events-status-pills button')];
    assert.ok(buttons.some(button => button.textContent === 'Draft 1'));
    assert.ok(buttons.some(button => button.textContent === 'Confirmed 1'));
    assert.ok(buttons.some(button => button.textContent === 'Submitted 0'));
    filled.window.close();
  } finally { await server.close(); }
});

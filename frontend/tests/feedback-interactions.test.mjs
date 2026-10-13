// npm install --prefix frontend/node_modules/.feedback-qa jsdom --no-save --package-lock=false
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';

test('popups, confirmation choices and authenticated retries work together', async t => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const originals = { window: globalThis.window, document: globalThis.document,
    sessionStorage: globalThis.sessionStorage, fetch: globalThis.fetch, act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.sessionStorage = dom.window.sessionStorage;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  // jsdom lacks native dialog rendering. Exercise the actual React queue and
  // choice handlers; browser focus trapping/appearance still need a browser.
  dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  dom.window.HTMLDialogElement.prototype.close = function () { this.open = false; };
  sessionStorage.setItem('auth_session', JSON.stringify({ access_token: 'expired-token', refresh_token: 'refresh-token' }));
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  let root;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { FeedbackProvider, useFeedback } = await server.ssrLoadModule('/src/components/FeedbackProvider.jsx');
    const { AuthProvider, useAuth } = await server.ssrLoadModule('/src/auth/AuthContext.jsx');
    let controls;
    function Harness() { controls = { ...useFeedback(), ...useAuth() }; return h('p', null, 'Test workspace'); }
    root = createRoot(document.getElementById('root'));
    await act(async () => root.render(h(FeedbackProvider, null, h(AuthProvider, null, h(Harness)))));
    const click = async text => {
      const button = [...document.querySelectorAll('button')].find(node => node.textContent === text);
      assert.ok(button, `button ${text} exists`);
      await act(async () => button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    };
    const dismissAll = async () => {
      for (const button of [...document.querySelectorAll('[aria-label="Dismiss notification"]')]) {
        await act(async () => button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
      }
    };

    await t.test('session refresh announces only the final successful action', async () => {
      let sends = 0;
      let refreshes = 0;
      globalThis.fetch = async (url, options) => {
        if (url === '/api/refresh') {
          refreshes++;
          return new Response(JSON.stringify({ access_token: 'fresh-token', refresh_token: 'new-refresh' }), { status: 200 });
        }
        sends++;
        if (options.headers.get('Authorization') === 'Bearer expired-token') return new Response('{}', { status: 401 });
        return new Response(JSON.stringify({ message: 'Draft saved.' }), { status: 200 });
      };
      await act(async () => controls.api('/api/event-requests', { method: 'POST', body: { save_as_draft: true } }));
      assert.equal(sends, 2);
      assert.equal(refreshes, 1);
      assert.equal(document.querySelectorAll('.feedback-toast').length, 1);
      assert.match(document.querySelector('.feedback-toast').textContent, /Draft saved/);
      await dismissAll();
    });
    await t.test('failed actions show dismissible errors while background refreshes stay quiet', async () => {
      globalThis.fetch = async () => new Response(JSON.stringify({ error: 'Only Technical Support Staff can reserve equipment.' }), { status: 403 });
      await act(async () => assert.rejects(controls.api('/api/equipment/reservations', { method: 'POST', body: {} }), /Technical Support/));
      assert.equal(document.querySelectorAll('[role="alert"]').length, 1);
      await dismissAll();
      globalThis.fetch = async () => new Response('{}', { status: 200 });
      await act(async () => controls.api('/api/events/status-refresh', { method: 'POST', body: {} }));
      assert.equal(document.querySelectorAll('.feedback-toast').length, 0);
      globalThis.fetch = async () => { throw Object.assign(new Error('Aborted'), { name: 'AbortError' }); };
      await act(async () => assert.rejects(controls.api('/api/events/1', { method: 'PATCH', body: {} }), /Aborted/));
      assert.equal(document.querySelectorAll('.feedback-toast').length, 0);
    });
    await t.test('queued confirmations resolve independently and cancellation never accepts the action', async () => {
      let first, second;
      await act(async () => {
        first = controls.confirm('Delete draft?', { title: 'Delete draft', confirmLabel: 'Delete', destructive: true });
        second = controls.confirm('Cancel event?', { title: 'Cancel event', confirmLabel: 'Cancel event' });
      });
      assert.equal(document.querySelector('dialog').open, true);
      assert.match(document.querySelector('dialog').textContent, /Delete draft/);
      await click('Go back'); assert.equal(await first, false);
      assert.match(document.querySelector('dialog').textContent, /Cancel event/);
      await click('Cancel event'); assert.equal(await second, true);
      assert.equal(document.querySelector('dialog'), null);
      let escape;
      await act(async () => { escape = controls.confirm('Delete venue?'); });
      await act(async () => document.querySelector('dialog').dispatchEvent(new dom.window.Event('cancel', { cancelable: true })));
      assert.equal(await escape, false);
    });
    await t.test('native form validation shows a useful popup', async () => {
      const input = document.createElement('input');
      document.querySelector('.feedback-app').append(input);
      await act(async () => input.dispatchEvent(new dom.window.Event('invalid', { bubbles: false, cancelable: true })));
      assert.match(document.querySelector('[role="alert"]').textContent, /required information/);
      await dismissAll();
    });
  } finally {
    if (root) { const { act } = await import('react'); await act(async () => root.unmount()); }
    await server.close();
    dom.window.close();
    globalThis.window = originals.window;
    globalThis.document = originals.document;
    globalThis.sessionStorage = originals.sessionStorage;
    globalThis.fetch = originals.fetch;
    globalThis.IS_REACT_ACT_ENVIRONMENT = originals.act;
  }
});

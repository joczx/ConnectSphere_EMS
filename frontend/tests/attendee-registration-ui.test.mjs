import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';

test('attendee search and status filters preserve accurate registration cards', async () => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  const now = Date.now();
  const iso = days => new Date(now + days * 86400000).toISOString();
  const events = [
    { event_id: 1, event_name: 'Community Technology Fair', description: 'Explore ideas, meet local makers and discover what is next in technology.', venues: ['Community Hall'], status: 'confirmed', start_datetime: iso(10), end_datetime: iso(10.25), registration_opens_at: iso(-1), registration_closes_at: iso(8), capacity: 200, available_capacity: 173, waiting_list_enabled: true },
    { event_id: 2, event_name: 'Creative Connections Workshop', description: 'An afternoon of hands-on activities and conversations with fellow creatives.', venues: ['Design Studio'], status: 'confirmed', start_datetime: iso(15), end_datetime: iso(15.1), registration_opens_at: iso(-1), registration_closes_at: iso(12), capacity: 40, available_capacity: 12 },
  ];
  const registrations = [
    { ...events[0], status: 'registered', event_status: 'confirmed' },
    { ...events[1], status: 'waiting_list', event_status: 'confirmed' },
    { ...events[0], event_id: 3, event_name: 'Community Open Day', status: 'withdrawn', event_status: 'cancelled' },
  ];
  globalThis.__attendeeUIAuth = { api: async path => {
    if (path === '/api/my-registrations') return { registrations };
    if (path === '/api/registration-events') return { events };
    throw Error('Unexpected request ' + path);
  } };
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)), configFile: false,
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    esbuild: { jsx: 'automatic' },
    plugins: [{ name: 'attendee-ui-test', enforce: 'pre',
      resolveId(id) {
        if (id.endsWith('/auth/AuthContext')) return '\0attendee-ui-auth';
        if (id.endsWith('/components/Navbar')) return '\0attendee-ui-navbar';
      },
      load(id) {
        if (id === '\0attendee-ui-auth') return 'export const useAuth = () => globalThis.__attendeeUIAuth;';
        if (id === '\0attendee-ui-navbar') return 'export default function Navbar() { return null; }';
      },
    }],
  });
  let root, browser;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { MemoryRouter } = await import('react-router-dom');
    root = createRoot(document.getElementById('root'));
    const render = async name => {
      const { default: Page } = await server.ssrLoadModule(`/src/pages/${name}.jsx`);
      await act(async () => root.render(h(MemoryRouter, null, h(Page, { key: name }))));
    };
    const search = async value => act(async () => {
      const input = document.querySelector('input[type="search"]');
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, value);
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    });
    const cards = () => [...document.querySelectorAll('.attendee-card')];
    const capture = async name => {
      if (process.env.ATTENDEE_UI_SCREENSHOTS !== '1') return;
      const { readFile, readdir, mkdir } = await import('node:fs/promises');
      const { chromium } = await import('@playwright/test');
      browser ||= await chromium.launch({ headless: true, ...(process.env.ATTENDEE_UI_BROWSER ? { channel: process.env.ATTENDEE_UI_BROWSER } : {}) });
      const assets = new URL('../dist/assets/', import.meta.url);
      const stylesheet = (await readdir(assets)).find(path => path.endsWith('.css'));
      const css = await readFile(new URL(stylesheet, assets), 'utf8');
      const directory = new URL('../../outputs/attendee-ui/', import.meta.url);
      await mkdir(directory, { recursive: true });
      for (const width of [1280, 390]) {
        const page = await browser.newPage({ viewport: { width, height: 980 } });
        await page.setContent(`<html><head><style>${css}</style></head><body>${document.getElementById('root').innerHTML}</body></html>`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: horizontal overflow at ${width}`);
        await page.screenshot({ path: fileURLToPath(new URL(`${name}-${width}.png`, directory)), fullPage: true });
        await page.close();
      }
    };
    await render('MyRegistrations');
    assert.equal(cards().length, 3);
    await capture('MyRegistrations');
    const waitlisted = [...document.querySelectorAll('[aria-pressed]')].find(button => button.textContent.startsWith('Waitlisted'));
    await act(async () => waitlisted.click());
    assert.equal(cards().length, 1);
    assert.ok(cards()[0].textContent.includes('Registration status: Waitlisted'));
    await search('no match');
    assert.equal(cards().length, 0);
    assert.ok(document.body.textContent.includes('No matching registrations'));
    await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent === 'Clear filters').click());
    assert.equal(cards().length, 3);
    await render('AttendeeEvents');
    assert.equal(cards().length, 2);
    await capture('AttendeeEvents');
    await search('design studio');
    assert.equal(cards().length, 1);
    assert.ok(cards()[0].textContent.includes('Creative Connections Workshop'));
    await search('no match');
    assert.ok(document.body.textContent.includes('No matching events'));
    await search('');
    events[0].my_registration = 'withdrawn';
    await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent === 'Refresh').click());
    const withdrawnCard = cards().find(card => card.textContent.includes('Community Technology Fair'));
    assert.ok(withdrawnCard.textContent.includes('Open for registration'));
    assert.ok(withdrawnCard.textContent.includes('Registration status: Withdrawn'));
    assert.ok(withdrawnCard.textContent.includes('Your registration has been withdrawn.'));
    const registerAgain = [...withdrawnCard.querySelectorAll('button')].find(button => button.textContent.startsWith('Register'));
    assert.ok(registerAgain);
    assert.equal(registerAgain.disabled, false);
  } finally {
    if (root) { const { act } = await import('react'); await act(async () => root.unmount()); }
    if (browser) await browser.close();
    await server.close(); dom.window.close();
    Object.assign(globalThis, { window: previous.window, document: previous.document, IS_REACT_ACT_ENVIRONMENT: previous.act });
    delete globalThis.__attendeeUIAuth;
  }
});

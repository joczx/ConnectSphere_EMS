import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';
import { hasAccess, rolesForPath } from '../src/auth/access.js';

test('sidebar groups every role application once and hides inaccessible and empty categories', async () => {
  const previous = globalThis.__sidebarTestAuth;
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    plugins: [{ name: 'sidebar-test-auth', enforce: 'pre',
      resolveId(id) { if (id.endsWith('/auth/AuthContext')) return '\0sidebar-test-auth'; },
      load(id) { if (id === '\0sidebar-test-auth') return 'export const useAuth = () => globalThis.__sidebarTestAuth;'; },
    }],
  });
  try {
    const { createElement: h } = await import('react');
    const { renderToString } = await import('react-dom/server');
    const { StaticRouter } = await import('react-router-dom');
    const { default: AppShell } = await server.ssrLoadModule('/src/components/AppShell.jsx');
    const { HOME_APPS, APP_CATEGORIES } = await server.ssrLoadModule('/src/config/apps.js');
    for (const app of HOME_APPS) assert.ok(APP_CATEGORIES.some(category => category.id === app.category), app.id);
    const cases = [
      [['Attendee'], ['Registration']],
      [['Event Organiser'], ['Events']],
      [['Event Coordinator'], ['Events', 'Equipment', 'Venues']],
      [['Event Coordinator Lead'], ['Events']],
      [['Technical Support Staff'], ['Events', 'Equipment']],
      [['Venue Staff'], ['Events', 'Venues']],
      [['Safety Officer'], ['Events', 'Safety']],
      [['Attendee', 'Event Coordinator'], ['Events', 'Registration', 'Equipment', 'Venues']],
    ];
    for (const [roles, labels] of cases) {
      const canAccess = path => hasAccess(roles, rolesForPath(path));
      globalThis.__sidebarTestAuth = { canAccess, session: { user: { email: 'test@example.com' } }, signOut() {} };
      const dom = new jsdom.JSDOM(renderToString(h(StaticRouter, { location: '/home' }, h(AppShell, null, 'Workspace'))));
      const document = dom.window.document;
      assert.deepEqual([...document.querySelectorAll('.sidebar-group-heading')].map(item => item.textContent), labels, roles.join(', '));
      const links = [...document.querySelectorAll('.sidebar-group a')].map(item => item.getAttribute('href'));
      assert.deepEqual(links.slice().sort(), HOME_APPS.filter(app => canAccess(app.path)).map(app => app.path).sort());
      assert.equal(new Set(links).size, links.length);
      assert.ok(document.querySelector('nav > a[href="/home"]'));
      dom.window.close();
    }
  } finally {
    await server.close();
    globalThis.__sidebarTestAuth = previous;
  }
});

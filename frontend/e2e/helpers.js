import { readFileSync } from 'node:fs';
import { DateTime } from 'luxon';

export const account = role => {
  const key = 'INTEGRATION_' + role.toUpperCase().replaceAll(' ', '_');
  return { email: process.env[`${key}_EMAIL`], password: process.env[`${key}_PASSWORD`] };
};

// `who` is a role name, or an account from the fixtures ({ email, password }).
export async function signIn(page, who) {
  const { email, password } = typeof who === 'string' ? account(who) : who;
  // Sign out whoever a previous step signed in, or '/' skips straight to Home.
  await page.goto('/');
  await page.evaluate(() => sessionStorage.clear());
  await page.goto('/');
  await page.reload();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(/#\/home$/);
}

// Test data only: the secret key bypasses Row Level Security.
export async function admin(path, { method = 'GET', body } = {}) {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const response = await fetch(process.env.SUPABASE_URL + path, {
    method,
    body: body && JSON.stringify(body),
    headers: { apikey: key, Authorization: `Bearer ${key}`,
               'Content-Type': 'application/json', Prefer: 'return=representation' },
  });
  if (!response.ok) throw new Error(`${method} ${path}: ${response.status} ${await response.text()}`);
  const text = await response.text();
  return text ? JSON.parse(text) : [];
}

export async function userId(role) {
  const rows = await admin(`/rest/v1/users?select=user_id&email=eq.${encodeURIComponent(account(role).email)}`);
  return rows[0].user_id;
}

// The events and accounts global-setup.js created for this run.
export const FIXTURES_FILE = new URL('./.fixtures.json', import.meta.url);
export const fixtures = () => JSON.parse(readFileSync(FIXTURES_FILE, 'utf8'));

// Times as the pages show them.
export const registrationDate = value =>
  DateTime.fromISO(value).setZone('Asia/Singapore').toFormat('dd LLL yyyy, HH:mm') + ' SGT';
export const eventDate = value => new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
}).format(new Date(value));
// A value for a datetime-local input, in Singapore time.
export const inputTime = value => value.setZone('Asia/Singapore').toFormat("yyyy-MM-dd'T'HH:mm");

// The card for one event on the attendee Event registration page.
export const eventCard = (page, event) =>
  page.locator('article').filter({ has: page.getByRole('heading', { name: event.event_name }) });

// Calls the Flask API directly as `role`, for arranging a step a test is not about.
export async function apiAs(request, role, method, path, data) {
  const login = await request.post('http://127.0.0.1:5000/api/login', { data: account(role) });
  const { access_token: token } = await login.json();
  const response = await request.fetch('http://127.0.0.1:5000' + path, {
    method, data, headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) throw new Error(`${method} ${path}: ${response.status()} ${await response.text()}`);
  return response.json();
}

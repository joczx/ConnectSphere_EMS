import { test, expect } from '@playwright/test';
import { account, signIn } from './helpers.js';

// SCRUM-6 AC1/2/4/5: real authentication, assigned role and route guards.
for (const [role, allowed, heading, forbidden] of [
  ['Attendee','/event-registration','Event registration','/events'],
  ['Event Organiser','/event-requests/new','New event request','/equipment'],
  ['Event Coordinator','/review-event-requests','Review event requests','/event-registration'],
  ['Event Coordinator Lead','/assign-event-coordinators','Assign Event Coordinators','/event-registration'],
  ['Venue Staff','/review-venue-bookings','Review venue bookings','/event-registration'],
  ['Technical Support Staff','/equipment','Equipment Requests','/event-registration'],
  ['Safety Officer','/operational-safety-reviews','Operational safety reviews','/event-registration'],
]) {
  test(`SCRUM-6: ${role} receives the correct workspace and is refused a forbidden URL`, async ({ page }) => {
    await signIn(page, role);
    await expect(page.locator('.account-menu-roles')).toContainText(role);
    await page.goto('/#' + allowed);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await page.reload(); await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await page.goto('/#' + forbidden); await expect(page).toHaveURL(/#\/home$/);
    await expect(page.locator('.account-menu-roles')).toContainText(role);
  });
}
// AC3: real invalid credential response stays on login with an error.
test('SCRUM-6: incorrect credentials show an error and do not open protected information', async ({ page }) => {
  await page.goto('/'); await page.getByLabel('Email').fill(account('Attendee').email);
  await page.getByLabel('Password').fill('intentionally-wrong-e2e-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toHaveText('Incorrect email or password. Please try again.');
  await page.goto('/#/my-registrations'); await expect(page.getByLabel('Password')).toBeVisible();
});

// SCRUM-6 AC5: bypassing navigation still cannot read another role's API data.
for (const [role, path] of [['Attendee', '/api/events/1/registrations'], ['Event Organiser', '/api/my-registrations'], ['Event Coordinator', '/api/registration-events']]) {
  test(`SCRUM-6: backend refuses ${role} at ${path}`, async ({ page }) => {
    const login = page.waitForResponse(response => new URL(response.url()).pathname === '/api/login');
    await signIn(page, role);
    const { access_token: token } = await (await login).json();
    const result = await page.evaluate(async ({ path, token }) => {
      const response = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
      return { status: response.status, body: await response.json() };
    }, { path, token });
    expect(result.status).toBe(403); expect(Object.keys(result.body)).toEqual(['error']);
  });
}

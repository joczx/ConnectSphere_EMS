// SCRUM-214 Set and Update Registration Period
//   AC1  The Organiser can set registration opening and closing dates and times.
//   AC2  The closing date and time must be after the opening date and time.
//   AC3  The Organiser can update the period before or during the registration period.
//   AC4  The Organiser can choose whether to enable a waiting list at capacity.
//   AC5  Attendees can only register within the registration period.
//   AC6  The updated period is reflected in the event information Attendees see.
//   AC7  A message is shown when registration is not yet open or has closed.
import { test, expect } from '@playwright/test';
import { DateTime } from 'luxon';
import { account, apiAs, eventCard, fixtures, inputTime, registrationDate, signIn } from './helpers.js';

let data;
test.beforeAll(() => { data = fixtures(); });

async function openForm(page, event) {
  await signIn(page, 'Event Organiser');
  await page.goto(`/#/events/${event.event_id}`);
  await page.getByRole('button', { name: 'Set or update registration' }).click();
}

const periodSection = page =>
  page.locator('section').filter({ has: page.getByRole('heading', { name: 'Registration period' }) });

async function openCatalogue(page) {
  const [response] = await Promise.all([
    page.waitForResponse(response => response.url().endsWith('/api/registration-events')
      && response.request().method() === 'GET'),
    page.goto('/#/event-registration'),
  ]);
  expect(response.status()).toBe(200);
  await expect(eventCard(page, data.open)).toBeVisible();
}

// E2E-RPD-001 (AC2): a closing time before the opening time is refused.
test('refuses a closing time before the opening time', async ({ page }) => {
  await openForm(page, data.not_open);
  const opens = DateTime.now().plus({ days: 3 });
  await page.getByLabel('Registration opens').fill(inputTime(opens));
  await page.getByLabel('Registration closes').fill(inputTime(opens.minus({ days: 1 })));
  await page.getByRole('button', { name: 'Save registration settings' }).click();

  await expect(periodSection(page).getByRole('alert')).toHaveText('Registration must close after it opens.');
});

// E2E-RPD-002 (AC1, AC3, AC4, AC6): before registration opens, the Organiser sets new
// times and turns on the waiting list; the Attendee then sees the new period.
test('sets the period and waiting list, and Attendees see the change', async ({ page, request }) => {
  try {
    await signIn(page, 'Attendee');
    await openCatalogue(page);
    await expect(eventCard(page, data.not_open)).toHaveCount(0);
    await openForm(page, data.not_open);
    const opens = DateTime.now().minus({ hours: 1 }).startOf('minute');
    const closes = opens.plus({ days: 1 });
    await page.getByLabel('Registration opens').fill(inputTime(opens));
    await page.getByLabel('Registration closes').fill(inputTime(closes));
    await page.getByLabel('Enable a waiting list when capacity is reached').check();
    await page.getByRole('button', { name: 'Save registration settings' }).click();

    await expect(periodSection(page).getByRole('status')).toHaveText('Registration settings saved.');
    await expect(periodSection(page)).toContainText(registrationDate(opens.toISO()));
    await expect(periodSection(page)).toContainText('Enabled when capacity is reached');

    await signIn(page, 'Attendee');
    await openCatalogue(page);
    const card = eventCard(page, data.not_open);
    await expect(card).toContainText(`Registration opens: ${registrationDate(opens.toISO())}`);
    await expect(card).toContainText(`Registration closes: ${registrationDate(closes.toISO())}`);
    await expect(card).toContainText('Waiting list: Enabled');
    await expect(card).toContainText('Registration is open.');
    await expect(card.getByRole('button', { name: /^Register/ })).toBeEnabled();
  } finally {
    await apiAs(request, 'Event Organiser', 'PATCH', `/api/events/${data.not_open.event_id}/registration-period`, {
      registration_opens_at: data.not_open.registration_opens_at,
      registration_closes_at: data.not_open.registration_closes_at,
      waiting_list_enabled: data.not_open.waiting_list_enabled,
    });
  }
});

// E2E-RPD-003 (AC3): during registration, the Organiser extends the closing time.
test('updates the period while registration is open', async ({ page }) => {
  await openForm(page, data.full);
  const closes = DateTime.now().plus({ days: 6 }).startOf('minute');
  await page.getByLabel('Registration closes').fill(inputTime(closes));
  await page.getByRole('button', { name: 'Save registration settings' }).click();

  await expect(periodSection(page).getByRole('status')).toHaveText('Registration settings saved.');
  await expect(periodSection(page)).toContainText(registrationDate(closes.toISO()));
});

// E2E-RPD-004 (AC5, AC7): future and closed periods are hidden; direct attempts are refused.
test('hides future periods and returns period refusal messages', async ({ page, request }) => {
  await signIn(page, 'Attendee');
  await openCatalogue(page);

  const login = await request.post('http://127.0.0.1:5000/api/login', { data: account('Attendee') });
  expect(login.ok()).toBeTruthy();
  const { access_token: token } = await login.json();
  for (const [event, message] of [[data.not_open, 'Registration is not yet open.'],
    [data.closed, 'Registration has closed.']]) {
    await expect(eventCard(page, event)).toHaveCount(0);
    const response = await request.post(`http://127.0.0.1:5000/api/events/${event.event_id}/registrations`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { full_name: 'Period Test Attendee', contact_email: 'period@connectsphere.invalid', contact_phone: '+65 6123 4567' },
    });
    expect(response.status()).toBe(409);
    expect((await response.json()).error).toBe(message);
  }
});

// E2E-RPD-005 (AC1): an event still in planning cannot have its period set yet, and says so.
test('explains that registration is set after the event is confirmed', async ({ page }) => {
  await signIn(page, 'Event Organiser');
  await page.goto(`/#/events/${data.planning.event_id}`);

  await expect(page.getByText('Registration timing can be configured after the safety review is approved'))
    .toBeVisible();
  await expect(page.getByRole('button', { name: 'Set or update registration' })).toHaveCount(0);
});

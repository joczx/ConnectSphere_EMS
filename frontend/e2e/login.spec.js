import { test, expect } from '@playwright/test';
import { account, signIn } from './helpers.js';

// E2E-LOGIN-001 (AC1): a valid login lands on the home page.
test('valid login opens the home page', async ({ page }) => {
  await signIn(page, 'Event Coordinator');
  await expect(page).toHaveURL(/#\/home$/);
});

// E2E-LOGIN-002 (AC3): a wrong password shows an error on screen.
test('wrong password shows an error', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill(account('Event Coordinator').email);
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('main').getByRole('alert'))
    .toHaveText('Incorrect email or password. Please try again.');
});

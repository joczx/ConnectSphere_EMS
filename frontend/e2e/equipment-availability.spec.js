import { test, expect, signIn, inputTime } from './story-fixtures.js';
import { DateTime } from 'luxon';

// SCRUM-15 AC1/3/4: real inventory and requested quantity, no mocked catalogue.
test('SCRUM-15: technical support checks a unique equipment model', async ({ page, story }) => {
  const item = await story.item();
  const start = DateTime.now().plus({ days: 100 });
  await signIn(page, 'Technical Support Staff'); await page.goto('/#/equipment-availability');
  await page.getByLabel('Equipment type').selectOption(item.equipment_type);
  await page.getByLabel('Requested quantity').fill('2');
  await page.getByLabel('Required start date and time').fill(inputTime(start));
  await page.getByLabel('Required end date and time').fill(inputTime(start.plus({ hours: 2 })));
  await page.getByRole('button', { name: 'Check availability', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Availability results' })).toBeVisible();
  await expect(page.getByRole('main')).toContainText(item.equipment_type);
  await expect(page.getByRole('main')).toContainText('10');
});

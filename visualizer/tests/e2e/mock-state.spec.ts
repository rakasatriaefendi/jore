import { expect, test } from '@playwright/test';

test('development mock controls keep labels and selection in sync', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));

  await page.goto('/');
  const controls = page.getByRole('region', { name: 'Mock visual events' });
  await expect(controls).toBeVisible();
  const agentChoice = controls.getByLabel('Agent');
  const stateChoice = controls.getByLabel('State');
  await expect(agentChoice.locator('option')).toHaveCount(5);
  await expect(stateChoice.locator('option')).toHaveCount(8);

  await agentChoice.selectOption('agent-frontend');
  const frontendLabel = page.getByTestId('agent-label-frontend');
  await page
    .getByRole('button', { name: 'Select Frontend, state Idle' })
    .click();
  const selected = page.getByRole('region', { name: 'Selected agent' });
  await expect(selected).toContainText('Frontend');

  for (const state of [
    'idle',
    'assigned',
    'walking',
    'working',
    'waiting',
    'reviewing',
    'success',
    'error',
  ]) {
    const label = state.charAt(0).toUpperCase() + state.slice(1);
    await stateChoice.selectOption(state);
    await controls.getByRole('button', { name: 'Apply' }).click();
    await expect(frontendLabel).toContainText(label);
    await expect(frontendLabel).toHaveAccessibleName(
      `Select Frontend, state ${label}`,
    );
    await expect(selected.locator('dd').nth(2)).toHaveText(label);
  }

  await expect(page.getByTestId('agent-label-supervisor')).toContainText(
    'Idle',
  );
  await controls.getByRole('button', { name: 'Reset selected' }).click();
  await expect(frontendLabel).toContainText('Idle');
  await expect(selected.locator('dd').nth(2)).toHaveText('Idle');

  await stateChoice.selectOption('working');
  await controls.getByRole('button', { name: 'Apply' }).click();
  await agentChoice.selectOption('agent-backend');
  await stateChoice.selectOption('error');
  await controls.getByRole('button', { name: 'Apply' }).click();
  await expect(page.getByTestId('agent-label-backend')).toContainText('Error');
  await controls.getByRole('button', { name: 'Reset all' }).click();
  for (const role of [
    'supervisor',
    'frontend',
    'backend',
    'documentation',
    'reviewer',
  ]) {
    await expect(page.getByTestId(`agent-label-${role}`)).toContainText('Idle');
  }
  await expect(selected.locator('dd').nth(2)).toHaveText('Idle');
  expect(errors).toEqual([]);
});

import { expect, test } from '@playwright/test';

test('loads the office and resets the camera without errors', async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });

  const response = await page.goto('/');
  expect(response?.ok()).toBe(true);
  await expect(page).toHaveTitle('JORE Visualizer');
  await expect(
    page.getByRole('heading', { name: 'JORE Visualizer', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('v1.13 Development', { exact: true }),
  ).toBeVisible();

  const root = page.getByRole('main', { name: '3D visualizer' });
  await expect(root).toBeVisible();
  const canvas = root.locator('canvas');
  await expect(canvas).toBeVisible();
  await expect
    .poll(() =>
      canvas.evaluate((element: HTMLCanvasElement) => {
        const context = element.getContext('webgl2');
        return (
          context !== null &&
          !context.isContextLost() &&
          element.width > 0 &&
          element.height > 0
        );
      }),
    )
    .toBe(true);
  await expect(page.getByRole('alert')).toHaveCount(0);
  const key = page.getByRole('complementary', { name: 'Office workstations' });
  await expect(key).toBeVisible();
  for (const name of [
    'Supervisor',
    'Frontend',
    'Backend',
    'Documentation',
    'Reviewer',
  ]) {
    await expect(key.getByText(name, { exact: true })).toBeVisible();
  }
  const resetView = page.getByRole('button', { name: 'Reset View' });
  await expect(resetView).toBeVisible();
  await resetView.click();
  await expect(canvas).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('office.png') });
  expect(errors).toEqual([]);
});

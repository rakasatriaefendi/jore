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
  for (const role of [
    'supervisor',
    'frontend',
    'backend',
    'documentation',
    'reviewer',
  ]) {
    await expect(page.getByTestId(`agent-label-${role}`)).toBeVisible();
  }
  await page.getByRole('button', { name: 'Select Supervisor' }).click();
  const selectedAgent = page.getByRole('region', { name: 'Selected agent' });
  await expect(selectedAgent).toBeVisible();
  await expect(selectedAgent.locator('dt').first()).toHaveText('Role');
  await expect(selectedAgent.locator('dd').first()).toHaveText('Supervisor');
  await expect(selectedAgent.locator('dd').nth(1)).toHaveText(
    'Supervisor workstation',
  );
  await expect(page.getByTestId('agent-label-supervisor')).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.getByRole('button', { name: 'Clear agent selection' }).click();
  await expect(selectedAgent).toHaveCount(0);
  await page.getByRole('button', { name: 'Select Backend' }).click();
  await expect(selectedAgent.locator('dd').first()).toHaveText('Backend');
  await expect(selectedAgent.locator('dd').nth(1)).toHaveText(
    'Backend workstation',
  );
  const backendLabel = page.getByTestId('agent-label-backend');
  const initialLabel = await backendLabel.boundingBox();
  const canvasBounds = await canvas.boundingBox();
  expect(initialLabel).not.toBeNull();
  expect(canvasBounds).not.toBeNull();
  if (!initialLabel || !canvasBounds)
    throw new Error('Office geometry is not visible');
  await page.mouse.move(
    canvasBounds.x + canvasBounds.width / 2,
    canvasBounds.y + canvasBounds.height / 2,
  );
  await page.mouse.wheel(0, -400);
  await expect
    .poll(async () => {
      const moved = await backendLabel.boundingBox();
      return moved
        ? Math.abs(moved.x - initialLabel.x) +
            Math.abs(moved.y - initialLabel.y)
        : 0;
    })
    .toBeGreaterThan(3);
  const resetView = page.getByRole('button', { name: 'Reset View' });
  await expect(resetView).toBeVisible();
  await resetView.click();
  await expect
    .poll(async () => {
      const restored = await backendLabel.boundingBox();
      return restored
        ? Math.abs(restored.x - initialLabel.x) +
            Math.abs(restored.y - initialLabel.y)
        : Infinity;
    })
    .toBeLessThan(2);
  await expect(canvas).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('office.png') });
  expect(errors).toEqual([]);
});

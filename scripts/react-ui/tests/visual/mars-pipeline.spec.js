import { test, expect } from '@playwright/test';

for (const theme of ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval']) {
  test(`${theme} Mars preparation dialog remains readable`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`/visual-fixtures.html?theme=${theme}&contract=mars-pipeline`);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('radio')).toHaveCount(2);
    await expect(dialog.getByRole('radio').last()).toBeChecked();
    await expect(dialog.getByRole('textbox').first()).toHaveValue(/ModContent\.fpk$/);
    const overflow = await dialog.evaluate((node) => ({
      width: node.scrollWidth - node.clientWidth,
      left: node.getBoundingClientRect().left,
      right: node.getBoundingClientRect().right,
    }));
    expect(overflow.width).toBeLessThanOrEqual(1);
    expect(overflow.left).toBeGreaterThanOrEqual(0);
    expect(overflow.right).toBeLessThanOrEqual(1280);
    await page.screenshot({ path: testInfo.outputPath(`mars-${theme}.png`), fullPage: true });
  });
}

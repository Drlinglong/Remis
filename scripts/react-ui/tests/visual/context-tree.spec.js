import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const viewports = [
  { id: 'wide', width: 1920, height: 1100 },
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'compact', width: 375, height: 900 },
];

for (const themeId of themes) {
  for (const viewport of viewports) {
    test(`${themeId} ${viewport.id} context tree stays readable`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=context-tree`);

      const fixture = page.getByTestId('context-tree-visual-fixture');
      await expect(fixture).toHaveAttribute('data-visual-ready', 'true');
      await expect(page.locator('html')).toHaveAttribute('data-theme', themeId);
      await expect(page.getByTestId('published-archive-toolbar')).toBeVisible();
      await expect(page.getByTestId('published-context-map')).toBeVisible();
      await expect(page.getByTestId('published-context-detail-empty')).toBeVisible();
      await expect(page.getByTestId('published-context-entities')).toBeVisible();
      await expect(page.getByTestId('published-context-group-group-unassigned')).toHaveAttribute(
        'data-group-kind',
        'needs-placement',
      );

      const layoutBox = await page.getByTestId('published-context-layout').boundingBox();
      expect(layoutBox.width / viewport.width).toBeGreaterThanOrEqual(0.9);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);

      await expect(page).toHaveScreenshot(`context-tree-${themeId}-${viewport.id}-overview.png`, { fullPage: true });

      if (viewport.id === 'wide') {
        await page.getByTestId('published-context-overview-rail').evaluate((rail) => {
          rail.scrollLeft = rail.scrollWidth;
        });
        await expect(page.getByTestId('published-context-group-group-unassigned')).toBeInViewport();
        await expect(page).toHaveScreenshot(`context-tree-${themeId}-${viewport.id}-exceptions.png`, { fullPage: true });
      }

      await page.getByTestId('published-context-fragment-fragment-signal').click();
      await expect(page.getByTestId('published-context-detail')).toContainText('解读求救讯号');
      const arrivalRail = page.getByTestId('published-context-mini-rail-group-arrival');
      if (viewport.width <= 1024) {
        await expect(arrivalRail).toBeHidden();
      } else {
        await expect(arrivalRail).toBeVisible();
      }
      await expect(page.getByRole('combobox', { name: '投递角色' })).toHaveValue('narrative');

      await expect(page).toHaveScreenshot(`context-tree-${themeId}-${viewport.id}-focused.png`, { fullPage: true });
    });
  }
}

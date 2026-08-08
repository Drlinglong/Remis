import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const viewports = [
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'compact', width: 720, height: 1100 },
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

      await expect(page).toHaveScreenshot(`context-tree-${themeId}-${viewport.id}-overview.png`, { fullPage: true });

      await page.getByTestId('published-context-fragment-fragment-signal').click();
      await expect(page.getByTestId('published-context-detail')).toContainText('解读求救讯号');
      await expect(page.getByTestId('published-context-mini-rail-group-arrival')).toBeVisible();
      await expect(page.getByRole('combobox', { name: '投递角色' })).toHaveValue('narrative');

      await expect(page).toHaveScreenshot(`context-tree-${themeId}-${viewport.id}-focused.png`, { fullPage: true });
    });
  }
}

import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const scenarios = ['active-partial', 'empty-error'];
const viewports = [
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'compact', width: 375, height: 900 },
];

for (const themeId of themes) {
  for (const scenario of scenarios) {
    for (const viewport of viewports) {
      test(`${themeId} ${scenario} ${viewport.id} keeps the Home dashboard contract`, async ({ page }) => {
        const errors = [];
        page.on('console', (message) => {
          if (message.type() === 'error') errors.push(message.text());
        });
        page.on('pageerror', (error) => errors.push(error.message));

        await page.clock.install({ time: new Date('2026-08-10T12:00:00Z') });
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=home-dashboard-${scenario}`);

        const fixture = page.getByTestId(`home-dashboard-${scenario}`);
        await expect(fixture).toHaveAttribute('data-visual-ready', 'true');
        await expect(page.locator('html')).toHaveAttribute('data-theme', themeId);
        await expect(page.locator('[data-remis-anchor="live-work"]')).toHaveCount(1);
        await expect(page.locator('[data-remis-action="primary"]')).toHaveCount(1);
        await expect(page.locator('[data-remis-scroll-owner="main-content"]')).toHaveCount(1);

        if (scenario === 'active-partial') {
          await expect(page.getByText('项目组合概览', { exact: true })).toBeVisible();
          await expect(page.getByText('星港远征：失落航道与群星彼端的超长项目名称验证', { exact: false }).first()).toBeVisible();
        } else {
          await expect(page.getByText('项目组合服务暂时离线；当前任务区仍然可用。')).toBeVisible();
          await expect(page.getByRole('button', { name: '继续项目' })).toBeVisible();
        }

        const result = await page.evaluate(() => {
          const documentFits = document.documentElement.scrollWidth <= document.documentElement.clientWidth;
          const overflowOwners = [...document.querySelectorAll('[data-testid^="home-dashboard-"] *')]
            .filter((element) => ['auto', 'scroll'].includes(getComputedStyle(element).overflowY));
          const escaped = [...document.querySelectorAll('[data-remis-surface]')]
            .some((surface) => surface.scrollWidth > surface.clientWidth + 1);
          return { documentFits, escaped, overflowOwners: overflowOwners.length };
        });

        expect(errors).toEqual([]);
        expect(result.documentFits).toBeTruthy();
        expect(result.overflowOwners).toBe(0);
        expect(result.escaped).toBeFalsy();

        await expect(page).toHaveScreenshot(
          `home-dashboard-${scenario}-${themeId}-${viewport.id}.png`,
          { fullPage: true },
        );
      });
    }
  }
}

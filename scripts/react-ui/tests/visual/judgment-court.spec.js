import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const viewports = [
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'wide', width: 2560, height: 1440 },
  { id: 'compact', width: 375, height: 900 },
];

for (const themeId of themes) {
  for (const viewport of viewports) {
    test(`${themeId} judgment court remains readable at ${viewport.id}`, async ({ page }) => {
      const consoleErrors = [];
      page.on('console', (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text());
      });
      await page.setViewportSize(viewport);
      await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=judgment-court`);

      const fixture = page.getByTestId('judgment-court-visual-fixture');
      await expect(fixture).toHaveAttribute('data-visual-ready', 'true');
      await expect(page.getByTestId('judgment-court-view-toolbar')).toBeVisible();
      await expect(page.getByTestId('neologism-docket-panel')).toBeVisible();
      await expect(page.getByTestId('neologism-candidate-anchor')).toBeVisible();
      await expect(page.getByTestId('neologism-decision-panel')).toBeVisible();
      await expect(page.getByTestId('neologism-evidence-source').first()).toBeVisible();
      expect(consoleErrors).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();

      if (viewport.id === 'wide') {
        const docketWidth = await page.getByTestId('neologism-docket-panel').evaluate(
          (element) => element.getBoundingClientRect().width,
        );
        const reviewWidth = await page.getByTestId('neologism-review-workspace').evaluate(
          (element) => element.getBoundingClientRect().width,
        );
        expect(docketWidth).toBeLessThan(450);
        expect(reviewWidth).toBeGreaterThan(2000);
      }

      await expect(page).toHaveScreenshot(
        `judgment-court-${themeId}-${viewport.id}.png`,
        { fullPage: true },
      );
    });
  }
}

for (const themeId of themes) {
  test(`${themeId} judgment court card view groups importance tiers`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=judgment-court`);
    await expect(page.getByTestId('judgment-court-visual-fixture')).toHaveAttribute('data-visual-ready', 'true');

    await page.getByText('卡片视图', { exact: true }).click();
    const cardView = page.getByTestId('judgment-court-card-view');
    await expect(cardView).toBeVisible();
    await expect(cardView.getByRole('button', { name: /A ·/ })).toHaveAttribute('aria-expanded', 'true');
    await expect(cardView.getByRole('button', { name: /B ·/ })).toHaveAttribute('aria-expanded', 'true');
    await expect(cardView.getByRole('button', { name: /C ·/ })).toHaveAttribute('aria-expanded', 'false');
    await expect(cardView.locator('#judgment-tier-C')).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();

    await expect(page).toHaveScreenshot(
      `judgment-court-cards-${themeId}-desktop.png`,
      { fullPage: true },
    );
  });
}

for (const themeId of themes) {
  test(`${themeId} judgment court uses a maximized 4K workspace`, async ({ page }) => {
    await page.setViewportSize({ width: 3840, height: 2160 });
    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=judgment-court`);
    await expect(page.getByTestId('judgment-court-visual-fixture')).toHaveAttribute('data-visual-ready', 'true');

    const docketWidth = await page.getByTestId('neologism-docket-panel').evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    const reviewWidth = await page.getByTestId('neologism-review-workspace').evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    expect(docketWidth).toBeLessThan(450);
    expect(reviewWidth).toBeGreaterThan(3200);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();
  });
}

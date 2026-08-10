import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const scenarios = ['active-list', 'dashboard-detail', 'kanban-normal', 'kanban-dragging'];
const viewports = [
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'compact', width: 375, height: 900 },
];

for (const themeId of themes) {
  for (const scenario of scenarios) {
    for (const viewport of viewports) {
      test(`${themeId} ${scenario} ${viewport.id} keeps ProjectManagement ownership contract`, async ({ page }) => {
        const consoleErrors = [];
        page.on('console', (message) => {
          if (message.type() === 'error') consoleErrors.push(message.text());
        });
        page.on('pageerror', (error) => consoleErrors.push(error.message));

        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=project-management-${scenario}`);

        const fixture = page.getByTestId(`project-management-${scenario}`);
        await expect(fixture).toHaveAttribute('data-visual-ready', 'true');
        await expect(page.locator('html')).toHaveAttribute('data-theme', themeId);

        if (scenario === 'active-list') {
          await expect(page.locator('#project-list-container')).toBeVisible();
          await expect(page.getByText('Expedition Demo — Project Management', { exact: true })).toBeVisible();
          await page.locator('#project-list-container .mantine-BackgroundImage-root').evaluate(async (element) => {
            const source = getComputedStyle(element).backgroundImage.match(/url\(["']?(.*?)["']?\)/)?.[1];
            if (!source) throw new Error('Project hero background image is missing');
            const image = new Image();
            image.src = source;
            await image.decode();
          });
        }

        if (scenario === 'dashboard-detail') {
          await expect(page.locator('#project-dashboard-tabs')).toBeVisible();
          await expect(page.locator('#project-dashboard-overview')).toBeVisible();
          await expect(page.locator('#project-dashboard-header')).toBeVisible();
        }

        if (scenario.startsWith('kanban-')) {
          await expect(page.getByTestId('project-management-kanban-board')).toBeVisible();
          await expect(page.locator('#kanban-board')).toBeVisible();
        }

        if (scenario === 'kanban-dragging') {
          const dragCard = page.locator('[class*="taskCard"]').filter({ hasText: 'events_l_english.yml' }).first();
          await expect(dragCard).toBeVisible();
          const cardBox = await dragCard.boundingBox();
          expect(cardBox).not.toBeNull();
          await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
          await page.mouse.down();
          await page.mouse.move(cardBox.x + cardBox.width / 2 + 80, cardBox.y + cardBox.height / 2 + 80, { steps: 6 });
          await expect(dragCard).toHaveClass(/taskCardDragging/);
        }

        expect(consoleErrors).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();

        await expect(page).toHaveScreenshot(
          `project-management-${scenario}-${themeId}-${viewport.id}.png`,
          { fullPage: true },
        );
      });
    }
  }
}

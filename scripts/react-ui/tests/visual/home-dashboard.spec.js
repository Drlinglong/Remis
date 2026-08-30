import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const scenarios = ['active-partial', 'empty-error'];
const viewports = [
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'compact', width: 375, height: 900 },
];

async function renderedContrast(locator) {
  return locator.evaluate((element) => {
    const parseColor = (value) => {
      const channels = value.match(/[\d.]+/g)?.map(Number) ?? [];
      return {
        r: channels[0] ?? 0,
        g: channels[1] ?? 0,
        b: channels[2] ?? 0,
        a: channels[3] ?? 1,
      };
    };
    const composite = (foreground, background) => {
      const alpha = foreground.a + background.a * (1 - foreground.a);
      if (alpha === 0) return { r: 255, g: 255, b: 255, a: 1 };
      return {
        r: (foreground.r * foreground.a
          + background.r * background.a * (1 - foreground.a)) / alpha,
        g: (foreground.g * foreground.a
          + background.g * background.a * (1 - foreground.a)) / alpha,
        b: (foreground.b * foreground.a
          + background.b * background.a * (1 - foreground.a)) / alpha,
        a: alpha,
      };
    };
    const luminance = ({ r, g, b }) => {
      const linear = [r, g, b].map((channel) => {
        const normalized = channel / 255;
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
    };

    const backgrounds = [];
    for (let node = element; node; node = node.parentElement) {
      backgrounds.push(parseColor(getComputedStyle(node).backgroundColor));
    }
    const background = backgrounds.reverse().reduce(
      (underlay, layer) => composite(layer, underlay),
      { r: 255, g: 255, b: 255, a: 1 },
    );
    const foreground = composite(parseColor(getComputedStyle(element).color), background);
    const brighter = Math.max(luminance(foreground), luminance(background));
    const darker = Math.min(luminance(foreground), luminance(background));
    return (brighter + 0.05) / (darker + 0.05);
  });
}

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

        const paperActions = page.locator(
          '[data-remis-surface="paper"] [data-remis-action]',
        );
        const paperActionCount = await paperActions.count();
        expect(paperActionCount).toBeGreaterThan(0);
        const paperActionValues = await paperActions.evaluateAll((elements) => (
          elements.map((element) => element.getAttribute('data-remis-action'))
        ));
        expect(paperActionValues.filter((value) => !value?.startsWith('paper-'))).toEqual([]);
        for (let index = 0; index < paperActionCount; index += 1) {
          expect(await renderedContrast(paperActions.nth(index))).toBeGreaterThanOrEqual(4.5);
        }

        if (scenario === 'active-partial') {
          await expect(page.getByText('项目组合概览', { exact: true })).toBeVisible();
          await expect(page.getByText('星港远征：失落航道与群星彼端的超长项目名称验证', { exact: false }).first()).toBeVisible();
          const taskActions = page.locator(
            '[data-remis-task-summary="true"] [data-remis-action="paper-secondary"]',
          );
          const taskActionCount = await taskActions.count();
          expect(taskActionCount).toBeGreaterThan(0);
          for (let index = 0; index < taskActionCount; index += 1) {
            expect(await renderedContrast(taskActions.nth(index))).toBeGreaterThanOrEqual(4.5);
          }
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

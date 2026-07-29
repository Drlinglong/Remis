import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const viewports = [
  { id: 'desktop', width: 1440, height: 1100 },
  { id: 'compact', width: 720, height: 1100 },
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
      if (alpha === 0) {
        return { r: 255, g: 255, b: 255, a: 1 };
      }
      return {
        r: (
          foreground.r * foreground.a
          + background.r * background.a * (1 - foreground.a)
        ) / alpha,
        g: (
          foreground.g * foreground.a
          + background.g * background.a * (1 - foreground.a)
        ) / alpha,
        b: (
          foreground.b * foreground.a
          + background.b * background.a * (1 - foreground.a)
        ) / alpha,
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
    const background = backgrounds
      .reverse()
      .reduce(
        (underlay, layer) => composite(layer, underlay),
        { r: 255, g: 255, b: 255, a: 1 },
      );
    const foreground = composite(
      parseColor(getComputedStyle(element).color),
      background,
    );
    const brighter = Math.max(luminance(foreground), luminance(background));
    const darker = Math.min(luminance(foreground), luminance(background));
    return (brighter + 0.05) / (darker + 0.05);
  });
}

for (const themeId of themes) {
  for (const viewport of viewports) {
    test(`${themeId} ${viewport.id} visual contract remains stable`, async ({ page }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    await page.goto(`/visual-fixtures.html?theme=${themeId}`);
    const lab = page.getByTestId('visual-reliability-lab');
    await expect(lab).toHaveAttribute('data-visual-ready', 'true');
    await expect(page.locator('html')).toHaveAttribute('data-theme', themeId);

    const overflowOffenders = await page.evaluate(() => (
      [...document.querySelectorAll('body *')]
        .filter((element) => {
          const style = getComputedStyle(element);
          const clipsOrScrolls = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX);
          return !clipsOrScrolls && element.scrollWidth > element.clientWidth + 1;
        })
        .map((element) => ({
          tag: element.tagName,
          testId: element.getAttribute('data-testid'),
          className: typeof element.className === 'string' ? element.className : '',
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
        }))
    ));
    expect(overflowOffenders).toEqual([]);

    const pathBox = await page.getByTestId('long-windows-path').boundingBox();
    const paperBox = await page.getByTestId('paper-contract-sample').boundingBox();
    expect(pathBox).not.toBeNull();
    expect(paperBox).not.toBeNull();
    expect(pathBox.x).toBeGreaterThanOrEqual(paperBox.x);
    expect(pathBox.x + pathBox.width).toBeLessThanOrEqual(paperBox.x + paperBox.width);

    const scrollOwners = await page.getByTestId('docket-scroll-owner').evaluate((owner) => {
      const pane = owner.parentElement;
      return [...pane.querySelectorAll('*')].filter((element) => {
        const style = getComputedStyle(element);
        return ['auto', 'scroll'].includes(style.overflowY)
          && element.scrollHeight > element.clientHeight;
      }).length;
    });
    expect(scrollOwners).toBe(1);

    const normalTextSamples = [
      page.getByText('固定内容用于检测主题层级、长文本、交互状态和溢出回归。', { exact: true }),
      page.getByText('已扫描 12 个文件，发现 11 项变更。任务状态和下一步保持清晰。', { exact: true }),
      page.getByTestId('long-windows-path'),
      page.getByText('部署和覆盖操作必须先呈现预览及影响范围。', { exact: true }),
      page.getByText('如何处理这个术语冲突？', { exact: true }),
      page.getByText('最终翻译', { exact: true }),
    ];
    for (const sample of normalTextSamples) {
      await expect(sample).toBeVisible();
      expect(await renderedContrast(sample)).toBeGreaterThanOrEqual(4.5);
    }

    expect(consoleErrors).toEqual([]);

    await expect(page).toHaveScreenshot(
      `visual-contract-${themeId}-${viewport.id}.png`,
      {
      fullPage: true,
      },
    );
    });
  }
}

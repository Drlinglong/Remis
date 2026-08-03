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
  test(`${themeId} published archive preserves hierarchy and readability`, async ({ page }) => {
    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=published-archive`);
    const fixture = page.getByTestId('published-archive-visual-fixture');
    await expect(fixture).toHaveAttribute('data-visual-ready', 'true');
    await expect(page.locator('html')).toHaveAttribute('data-theme', themeId);

    const metadataDetails = page.getByTestId('mod-archive-metadata-details');
    const traceability = page.getByTestId('mod-archive-traceability');
    await expect(metadataDetails).not.toHaveAttribute('open', '');
    await expect(traceability).not.toHaveAttribute('open', '');
    await expect(page.getByText('2026-08-03 11:25', { exact: true })).toBeVisible();
    await expect(page.getByText('openrouter', { exact: true })).toBeVisible();
    await expect(page.getByText('openai/gpt-5.6-luna', { exact: true })).toBeVisible();

    await metadataDetails.locator('summary').click();
    await expect(page.getByText('完整档案分析', { exact: true })).toBeVisible();
    await expect(page.getByText('v0.0.1', { exact: true })).toBeVisible();
    await expect(page.getByTestId('mod-archive-prompt-example')).toContainText('System message:');
    await expect(page.getByText('context-synthesis-v3', { exact: true })).toHaveCount(0);
    await metadataDetails.locator('summary').click();

    const summaryKinds = await page.locator('[class*="summarySection"]').evaluateAll((sections) => (
      sections.map((section) => section.getAttribute('data-kind'))
    ));
    expect(summaryKinds).toEqual(['project', 'event', 'entity']);

    const entityList = page.locator('[data-kind="entity"] [class*="entryList"]');
    const entityColumns = await entityList.evaluate((element) => (
      getComputedStyle(element).gridTemplateColumns.split(' ').length
    ));
    expect(entityColumns).toBe(2);

    await traceability.locator('summary').first().click();
    const evidenceGroups = traceability.locator('details[class*="evidenceGroup"]');
    await expect(evidenceGroups).toHaveCount(6);
    for (const group of await evidenceGroups.all()) {
      await expect(group).not.toHaveAttribute('open', '');
    }
    await evidenceGroups.nth(1).locator('summary').click();

    const readableSamples = [
      page.getByText('源文件来源依据与可追溯性', { exact: true }),
      page.getByText('按项目、事件与实体检查每个展示对象的来源证据。', { exact: true }),
      page.getByText('remis_crisis', { exact: true }).first(),
    ];
    for (const sample of readableSamples) {
      await expect(sample).toBeVisible();
      expect(await renderedContrast(sample)).toBeGreaterThanOrEqual(4.5);
    }

    const overflowOffenders = await fixture.evaluate((root) => (
      [...root.querySelectorAll('*')]
        .filter((element) => {
          const style = getComputedStyle(element);
          const clipsOrScrolls = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX);
          return !clipsOrScrolls && element.scrollWidth > element.clientWidth + 1;
        })
        .map((element) => ({
          tag: element.tagName,
          className: typeof element.className === 'string' ? element.className : '',
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
        }))
    ));
    expect(overflowOffenders).toEqual([]);

    await expect(page).toHaveScreenshot(`published-archive-${themeId}.png`, { fullPage: true });
  });

  test(`${themeId} project glossary paper content remains readable`, async ({ page }) => {
    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=project-glossary`);
    const fixture = page.getByTestId('project-glossary-contrast-fixture');
    await expect(fixture).toHaveAttribute('data-visual-ready', 'true');

    const samples = [
      page.getByTestId('project-glossary-title'),
      page.getByTestId('project-glossary-description'),
      page.getByTestId('project-glossary-badge'),
      page.getByTestId('project-glossary-alert'),
    ];
    for (const sample of samples) {
      await expect(sample).toBeVisible();
      expect(await renderedContrast(sample)).toBeGreaterThanOrEqual(4.5);
    }
  });

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

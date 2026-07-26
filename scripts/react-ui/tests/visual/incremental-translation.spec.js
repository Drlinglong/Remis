import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const steps = ['project', 'config', 'prescan', 'execution'];

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
      return {
        r: (foreground.r * foreground.a + background.r * background.a * (1 - foreground.a)) / alpha,
        g: (foreground.g * foreground.a + background.g * background.a * (1 - foreground.a)) / alpha,
        b: (foreground.b * foreground.a + background.b * background.a * (1 - foreground.a)) / alpha,
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
    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
    return (values[0] + 0.05) / (values[1] + 0.05);
  });
}

for (const themeId of themes) {
  for (const step of steps) {
    test(`${themeId} ${step} keeps incremental content readable`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.goto(`/incremental-visual-fixtures.html?theme=${themeId}&step=${step}`);
      const lab = page.getByTestId('incremental-visual-lab');
      await expect(lab).toHaveAttribute('data-visual-ready', 'true');
      await expect(page.locator('html')).toHaveAttribute('data-theme', themeId);

      const overflowOffenders = await page.evaluate(() => (
        [...document.querySelectorAll('body *')]
          .filter((element) => {
            const style = getComputedStyle(element);
            const ownsOverflow = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX);
            return !ownsOverflow && element.scrollWidth > element.clientWidth + 1;
          })
          .map((element) => ({
            tag: element.tagName,
            className: typeof element.className === 'string' ? element.className : '',
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
          }))
      ));
      expect(overflowOffenders).toEqual([]);

      const samples = [
        page.getByRole('heading', { name: '增量翻译' }),
        page.getByText('真实关键子页面主题对比度与溢出夹具'),
      ];
      if (step === 'project') {
        samples.push(page.getByText('Project Remis - Demo Mod - Stellaris'));
      } else if (step === 'config') {
        samples.push(page.getByText('支持的增量工作流', { exact: true }));
      } else if (step === 'prescan') {
        samples.push(page.getByText('预扫描摘要', { exact: true }));
      } else {
        samples.push(page.getByText('任务正在后台运行。你可以安全离开此页面，并随时从任务中心查看进度。'));
      }

      for (const sample of samples) {
        await expect(sample).toBeVisible();
        expect(await renderedContrast(sample)).toBeGreaterThanOrEqual(4.5);
      }
    });
  }
}

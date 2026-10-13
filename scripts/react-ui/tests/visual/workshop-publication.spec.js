import { test, expect } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const prefix = '/api/steam-workshop/workspaces/visual-publication/publication';

async function mockPublication(page, outputs, calls) {
  await page.route(`**${prefix}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === 'POST') {
      calls.push(route.request().postDataJSON());
      return route.fulfill({ status: 409, json: { detail: 'Visual fixture: no real publication.' } });
    }
    return route.fulfill({ json: path.endsWith('/options') ? { outputs } : [] });
  });
}

function contrast(foreground, background) {
  const luminance = (color) => {
    const channels = color.match(/[\d.]+/g).slice(0, 3).map(Number).map((v) => {
      const c = v / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  };
  const a = luminance(foreground), b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

for (const theme of themes) {
  test(`${theme}: output selection, readable inputs and editable suggested tags`, async ({ page }) => {
    const calls = [];
    await mockPublication(page, [{ output_folder_name: 'test-translation' }], calls);
    await page.goto(`/visual-fixtures.html?theme=${theme}&contract=workshop-publication`);
    const output = page.getByRole('textbox', { name: '翻译输出包', exact: true });
    await expect(output).toBeEnabled();
    await output.click();
    await page.getByRole('option', { name: 'test-translation', exact: true }).click();
    await expect(output).toHaveValue('test-translation');
    await page.getByLabel('Steam App ID', { exact: true }).fill('529340');
    await page.getByLabel('创意工坊标题', { exact: true }).fill('Smoke title');
    await page.getByLabel('更新说明', { exact: true }).fill('Private test');
    const tags = page.getByRole('textbox', { name: '标签（逗号分隔）', exact: true });
    await tags.click();
    await page.getByRole('option', { name: 'Translation', exact: true }).click();
    await tags.fill('MyCustomTag');
    await tags.press('Enter');
    await tags.press('Escape');
    for (const label of ['Steam App ID', '创意工坊标题', 'Steam API 语言代码', '更新说明']) {
      const paint = await page.getByLabel(label, { exact: true }).evaluate((el) => {
        const s = getComputedStyle(el);
        return { foreground: s.color, background: s.backgroundColor };
      });
      expect(contrast(paint.foreground, paint.background), label).toBeGreaterThanOrEqual(4.5);
    }
    await page.getByRole('button', { name: '生成不可变发布预览', exact: true }).click();
    await expect.poll(() => calls.length).toBe(1);
    expect(calls[0].tags).toEqual(['Translation', 'MyCustomTag']);
    expect(calls[0].output_folder_name).toBe('test-translation');
    expect(calls[0].visibility).toBe('private');
  });
}

test('empty outputs explain the prerequisite and cannot create a preview', async ({ page }) => {
  await mockPublication(page, [], []);
  await page.goto('/visual-fixtures.html?theme=wwii&contract=workshop-publication');
  await expect(page.getByText(/没有找到已生成的翻译输出包/)).toBeVisible();
  await expect(page.getByRole('textbox', { name: '翻译输出包', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '生成不可变发布预览', exact: true })).toBeDisabled();
});

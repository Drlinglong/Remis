import { test, expect } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const prefix = '/api/steam-workshop/workspaces/visual-publication/publication';

async function mockPublication(page, outputs, calls) {
  await page.route(`**${prefix}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === 'POST') {
      calls.push(route.request().postDataJSON());
      return route.fulfill({ json: {
        status: 'preview', plan_id: 'visual-plan', allowed_actions: [],
        target: route.request().postDataJSON(), content_path: 'J:/fixture',
        file_count: 1, total_bytes: 20, validation: { entry_count: 1 },
        runtime: { ready: true, steam_id: 'test-account' }, fingerprint: 'a'.repeat(64),
        cover_version_id: 'test-cover', description: '[b]Remis Smoke Test 20261014[/b]',
        files: [{ path: 'test.yml', sha256: 'b'.repeat(64) }],
      } });
    }
    return route.fulfill({ json: path.endsWith('/options') ? { outputs, default_app_id: '529340', game_options: [
      { game_id: 'victoria3', app_id: 529340, name: 'Victoria 3' },
      { game_id: 'hoi4', app_id: 394360, name: 'Hearts of Iron IV' },
    ], runtime: { ready: true } } : [] });
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
    await expect(page.getByRole('textbox', { name: 'Steam App ID', exact: true })).toHaveValue('529340（维多利亚3）');
    await page.getByLabel('创意工坊标题', { exact: true }).fill('Smoke title');
    await page.getByLabel('更新说明', { exact: true }).fill('Private test');
    const tags = page.getByRole('textbox', { name: '标签（逗号分隔）', exact: true });
    await tags.click();
    await page.getByRole('option', { name: 'Translation', exact: true }).click();
    await tags.fill('MyCustomTag');
    await tags.press('Enter');
    await tags.press('Escape');
    for (const label of ['创意工坊标题', 'Steam API 语言代码', '更新说明']) {
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
    for (const text of ['SHA-256', 'a'.repeat(64), 'b'.repeat(64), 'Smoke title', 'Remis Smoke Test 20261014']) {
      const paint = await page.getByText(text, { exact: true }).first().evaluate((el) => {
        const foreground = getComputedStyle(el).color;
        let node = el, background;
        do { background = getComputedStyle(node).backgroundColor; node = node.parentElement; }
        while (node && (background === 'transparent' || background === 'rgba(0, 0, 0, 0)'));
        return { foreground, background };
      });
      expect(contrast(paint.foreground, paint.background), text).toBeGreaterThanOrEqual(4.5);
    }

  });
}

test('empty outputs explain the prerequisite and cannot create a preview', async ({ page }) => {
  await mockPublication(page, [], []);
  await page.goto('/visual-fixtures.html?theme=wwii&contract=workshop-publication');
  await expect(page.getByText(/没有找到已生成的翻译输出包/)).toBeVisible();
  await expect(page.getByRole('textbox', { name: '翻译输出包', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '生成不可变发布预览', exact: true })).toBeDisabled();
});

test('game selection switches presets and permits an explicit custom App ID', async ({ page }) => {
  await mockPublication(page, [], []);
  await page.goto('/visual-fixtures.html?theme=wwii&contract=workshop-publication');
  const game = page.getByRole('textbox', { name: 'Steam App ID', exact: true });
  await expect(game).toHaveValue('529340（维多利亚3）');
  await game.click();
  await page.getByRole('option', { name: '394360（钢铁雄心4）', exact: true }).click();
  await expect(game).toHaveValue('394360（钢铁雄心4）');
  await game.click();
  await page.getByRole('option', { name: '手动输入其他 App ID', exact: true }).click();
  const manual = page.getByRole('textbox', { name: '手动输入其他 App ID', exact: true });
  await expect(manual).toHaveValue('');
  await manual.fill('480');
  await expect(manual).toHaveValue('480');
});

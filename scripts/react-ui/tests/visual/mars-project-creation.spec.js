import { test, expect } from '@playwright/test';

test('Mars uses a single ordinary project form and prepares the selected folder', async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem('i18nextLng', 'zh'));
  const calls = [];
  await page.route('**/api/mars-pipeline/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push({ path, body: route.request().postDataJSON() });
    const body = path.endsWith('/input/inspect')
      ? { kind: 'archive', archive_path: 'J:/workshop/3816401225/ModContent.fpk' }
      : path.endsWith('/prepare/plan')
      ? { plan_id: 'visual-plan', source_blockers: [], review_items: [{ id: 'pending-review' }], allowed_actions: ['approve_preparation'] }
      : { status: 'prepared', project_id: 'visual-mars-project' };
    await route.fulfill({ json: body });
  });
  await page.goto('/visual-fixtures.html?theme=scifi&contract=mars-project-creation');
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await expect(page.getByText('源 CSV 表（可选）')).toHaveCount(0);
  await expect(page.getByText('源文本列')).toHaveCount(0);
  await page.getByLabel('项目名称', { exact: true }).fill('Grom');
  await page.getByRole('button', { name: '浏览', exact: true }).click();
  await expect(page.getByLabel('文件夹路径', { exact: true })).toHaveValue(/3816401225$/);
  expect(calls).toHaveLength(0);
  await page.getByRole('dialog').screenshot({ path: testInfo.outputPath('mars-create-project.png') });
  await page.getByRole('button', { name: '创建新项目', exact: true }).click();
  await expect(page.getByTestId('created-project')).toHaveText('visual-mars-project');
  expect(calls.map((call) => call.path)).toEqual([
    '/api/mars-pipeline/input/inspect', '/api/mars-pipeline/prepare/plan', '/api/mars-pipeline/prepare',
  ]);
  expect(calls[1].body.source_language).toBe('en');
  expect(calls[1].body.source_table).toBeUndefined();
  expect(calls[1].body.approved_ids).toBeUndefined();
});

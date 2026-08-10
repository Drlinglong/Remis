import { createInstance } from 'i18next';
import { describe, expect, it } from 'vitest';

import translationEN from '../locales/en/translation.json';
import translationZH from '../locales/zh/translation.json';

const buildI18n = async (lng, translation) => {
  const instance = createInstance();
  await instance.init({
    fallbackLng: 'en',
    lng,
    resources: { [lng]: { translation } },
  });
  return instance;
};

describe('project management workspace locale', () => {
  it('resolves the new workspace hierarchy in Chinese', async () => {
    const instance = await buildI18n('zh', translationZH);

    expect(instance.t('project_management.workspace_label')).toBe('项目档案馆');
    expect(instance.t('project_management.stage.scan')).toBe('扫描');
    expect(instance.t('project_management.kanban.empty_column')).toBe('将任务拖放到这里');
  });

  it('resolves interpolation in the English project count', async () => {
    const instance = await buildI18n('en', translationEN);

    expect(instance.t('project_management.project_count', { count: 3 })).toBe('3 projects');
  });
});

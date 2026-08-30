import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ConfigStep from './ConfigStep';

const t = (key, options) => options?.defaultValue || key;

function createForm() {
  const values = {
    api_provider: 'gemini',
    clean_source: false,
    custom_key: '',
    custom_name: '',
    custom_prefix: '',
    disguise_target_key: '',
    embedded_workshop_api_model: '',
    embedded_workshop_api_provider: '',
    embedded_workshop_enabled: true,
    embedded_workshop_follow_primary_settings: true,
    english_disguise: false,
    model_name: 'gemini-flash',
    mod_context: '',
    selected_glossary_ids: [],
    target_lang_codes: [],
    translation_batch_size_limit: '',
    translation_concurrency_limit: '',
    translation_context_mode: 'archive',
    translation_rpm_limit: '40',
    use_main_glossary: true,
    use_resume: false,
  };

  return {
    values,
    clearFieldError: vi.fn(),
    setFieldValue: vi.fn(),
    getInputProps: (name, options = {}) => (
      options.type === 'checkbox'
        ? { checked: Boolean(values[name]), onChange: vi.fn() }
        : { value: values[name] ?? '', onChange: vi.fn() }
    ),
    onSubmit: () => (event) => event.preventDefault(),
  };
}

describe('ConfigStep read-only project facts', () => {
  it('keeps selected project facts readable without making them editable', () => {
    render(
      <MantineProvider>
        <ConfigStep
          availableGlossaries={[]}
          availableModels={[{ value: 'gemini-flash', label: 'Gemini Flash' }]}
          checkpointHintInfo={null}
          config={{
            api_providers: [{ value: 'gemini', label: 'Gemini' }],
            game_profiles: { stellaris: { id: 'stellaris', name: 'Stellaris' } },
            languages: {
              en: { code: 'en', key: 'l_english', name: 'English' },
              zh: { code: 'zh-CN', key: 'l_simp_chinese', name: '简体中文' },
            },
          }}
          embeddedWorkshopModels={[]}
          form={createForm()}
          onSubmit={vi.fn()}
          selectedProject={{
            game_id: 'stellaris',
            label: '毒圣骑士-#198模组档案测试',
            source_language: 'en',
          }}
          selectedProjectId="project-198"
          t={t}
        />
      </MantineProvider>,
    );

    const projectName = screen.getByLabelText('form_label_project_name');
    const game = screen.getByLabelText('form_label_game');
    const sourceLanguage = screen.getByLabelText('form_label_source_language');

    expect(projectName).toHaveValue('毒圣骑士-#198模组档案测试');
    expect(game).toHaveValue('Stellaris');
    expect(sourceLanguage).toHaveValue('English');
    for (const field of [projectName, game, sourceLanguage]) {
      expect(field).toHaveAttribute('readonly');
      expect(field).toHaveAttribute('aria-readonly', 'true');
      expect(field).not.toBeDisabled();
    }
  });
});

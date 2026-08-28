import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ConfigStep from './ConfigStep';

const t = (key, options) => {
  if (typeof options === 'string') return options;
  return options?.defaultValue || key;
};

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
    translation_rpm_limit: '40',
    use_main_glossary: true,
    use_resume: false,
  };

  return {
    values,
    clearFieldError: vi.fn(),
    setFieldValue: vi.fn((name, value) => {
      values[name] = value;
    }),
    getInputProps: (name, options = {}) => {
      if (options.type === 'checkbox') {
        return {
          checked: Boolean(values[name]),
          onChange: options.onChange || vi.fn(),
        };
      }
      return {
        value: values[name] ?? '',
        onChange: vi.fn(),
      };
    },
    onSubmit: () => (event) => event.preventDefault(),
  };
}

describe('ConfigStep advanced disclosure', () => {
  it('keeps advanced fields mounted but visually collapsed until expanded', async () => {
    render(
      <MantineProvider>
        <ConfigStep
          availableGlossaries={[]}
          availableModels={[{ value: 'gemini-flash', label: 'Gemini Flash' }]}
          checkpointHintInfo={null}
          config={{
            api_providers: [{ value: 'gemini', label: 'Gemini' }],
            game_profiles: { vic3: { id: 'victoria3', name: 'Victoria 3' } },
            languages: {
              en: { code: 'en', key: 'l_english', name: 'English' },
              zh: { code: 'zh-CN', key: 'l_simp_chinese', name: '简体中文' },
            },
          }}
          embeddedWorkshopModels={[]}
          form={createForm()}
          onSubmit={vi.fn()}
          selectedProject={{
            game_id: 'vic3',
            label: 'Demo Project',
            source_language: 'zh-CN',
          }}
          selectedProjectId="project-1"
          t={t}
        />
      </MantineProvider>,
    );

    const promptField = screen.getByLabelText('form_label_additional_prompt');
    expect(promptField.closest('[data-collapsed]')).not.toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Advanced Options' }));

    expect(promptField.closest('[data-collapsed]')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Scan exact matches' })).toBeNull();

    fireEvent.click(screen.getByRole('button', {
      name: /translation_config\.reference_reuse/,
    }));

    expect(await screen.findByRole('button', { name: 'Scan exact matches' })).toBeInTheDocument();
  });
});

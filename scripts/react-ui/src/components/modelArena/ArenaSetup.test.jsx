import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArenaSetup from './ArenaSetup';

const t = (key, values = {}) => (
  key === 'model_arena.provider_number'
    ? `provider ${values.number}`
    : key === 'model_arena.seed'
      ? `seed:${values.seed}`
      : key === 'model_arena.output_sample'
        ? `sample ${values.number}`
    : key
);

describe('ArenaSetup provider availability', () => {
  it('explains unavailable providers and uses the shared source-language label', () => {
    render(
      <MantineProvider>
        <ArenaSetup
          t={t}
          projects={[{
            project_id: 'project-1',
            name: 'Victoria 3 demo',
            game_id: 'victoria3',
            source_language: 'zh-CN',
          }]}
          providers={[
            {
              value: 'deepseek',
              label: 'DeepSeek',
              configured: false,
              selected_model: 'deepseek-v4-pro',
            },
            {
              value: 'lm_studio',
              label: 'LM Studio',
              configured: true,
              selected_model: 'google/gemma-4-31b-qat',
            },
          ]}
          languages={{ en: 'English' }}
          values={{
            project_id: 'project-1',
            target_lang_code: 'en',
            sample_size: 6,
            use_project_context: true,
            contestants: [
              { provider_id: 'deepseek', model_id: 'deepseek-v4-pro' },
              { provider_id: 'lm_studio', model_id: 'google/gemma-4-31b-qat' },
            ],
          }}
          draft={null}
          loading={false}
          onChange={vi.fn()}
          onCreateDraft={vi.fn()}
          onResample={vi.fn()}
          onRequestStart={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('form_label_source_language: zh-CN')).toBeInTheDocument();
    expect(screen.getByDisplayValue('DeepSeek · api_key_not_configured')).toBeInTheDocument();
  });

  it('exposes the frozen seed, samples, features, and glossary evidence before calls', () => {
    const onEditDraft = vi.fn();
    render(
      <MantineProvider>
        <ArenaSetup
          t={t}
          projects={[{
            project_id: 'project-1',
            name: 'Stellaris demo',
            game_id: 'stellaris',
            source_language: 'en',
          }]}
          providers={[{
            value: 'lm_studio',
            label: 'LM Studio',
            configured: true,
            selected_model: 'model-a',
            available_models: ['model-a', 'model-b'],
          }]}
          languages={{ 'zh-CN': '简体中文' }}
          values={{
            project_id: 'project-1',
            target_lang_code: 'zh-CN',
            sample_size: 3,
            use_project_context: true,
            contestants: [
              { provider_id: 'lm_studio', model_id: 'model-a' },
              { provider_id: 'lm_studio', model_id: 'model-b' },
            ],
          }}
          draft={{
            run_id: 'run-1',
            status: 'draft',
            sample_seed: 'fixed-seed',
            sample_size: 3,
            eligible_count: 12,
            samples: [{
              sample_id: 'sample-1',
              ordinal: 0,
              source_text: 'Argentum-9 powers the fleet.',
              feature_tags: ['glossary_term', 'protected_format'],
            }],
            settings: {
              glossary_snapshot: {
                enabled: true,
                entry_count: 1091,
                matched_entry_count: 1,
                glossaries: [{
                  glossary_id: 4,
                  name: 'Stellaris Main Glossary',
                  entry_count: 1091,
                }],
              },
            },
          }}
          loading={false}
          onChange={vi.fn()}
          onCreateDraft={vi.fn()}
          onResample={vi.fn()}
          onEditDraft={onEditDraft}
          onRequestStart={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('seed:fixed-seed')).toBeInTheDocument();
    expect(screen.getByText('Stellaris Main Glossary · 1091')).toBeInTheDocument();
    expect(screen.getByText('model_arena.glossary_snapshot_title').closest('[role="alert"]'))
      .toHaveClass('model-arena-glossary-alert');
    expect(screen.getByText('model_arena.feature_glossary_term')).toBeInTheDocument();
    expect(screen.getByText('Argentum-9 powers the fleet.')).not.toBeVisible();

    const sampleControl = screen.getByRole('button', { name: /sample 1/i });
    fireEvent.click(sampleControl);
    expect(sampleControl).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.edit_configuration' }));
    expect(onEditDraft).toHaveBeenCalledOnce();
  });
});

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import GlossaryOperations from './GlossaryOperations';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => (
      typeof options === 'string' ? options : (options?.defaultValue || key)
    ),
    i18n: { language: 'en' },
  }),
}));

describe('GlossaryOperations editor entry', () => {
  it('opens AI inspection for the current glossary with explicit approval still required', async () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <GlossaryOperations
            selectedIds={[7]}
            glossaries={[{ glossary_id: 7, game_id: 'vic3', name: 'Core terminology' }]}
            targetLanguages={[{ code: 'en', name_local: 'English' }]}
            apiProviders={[{
              value: 'lm_studio',
              label: 'LM Studio',
              selected_model: 'local-model',
              available_models: ['local-model'],
            }]}
            operation={null}
            isMutating={false}
            onPreviewMerge={vi.fn()}
            onStartMerge={vi.fn()}
            onStartHealthCheck={vi.fn()}
            onLoadHealthHistory={vi.fn()}
            toolbarMode="health-only"
            defaultIncludeAiAdvice
          />
        </MemoryRouter>
      </MantineProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'AI inspection' }));

    expect(await screen.findByRole('checkbox', {
      name: 'Add advisory AI review after deterministic checks',
    })).toBeChecked();
    expect(screen.getByRole('checkbox', {
      name: 'I approve this model request. It may use a paid provider and will return suggestions only.',
    })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Start health task' })).toBeDisabled();
  });
});

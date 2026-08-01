import React from 'react';
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import LanguageTargetSelector from './LanguageTargetSelector';

const languages = {
  en: { code: 'en', key: 'l_english', name: 'English' },
  fr: { code: 'fr', key: 'l_french', name: 'Français' },
  zh: { code: 'zh-CN', key: 'l_simp_chinese', name: '简体中文' },
};

const t = (key, options) => {
  const labels = {
    initial_translation_clear_all: 'Clear all',
    initial_translation_select_all: 'Select all',
    initial_translation_target_none: 'No targets',
    initial_translation_target_required: 'Choose at least one target',
    initial_translation_target_section_title: 'Target languages',
  };
  if (key === 'initial_translation_target_selected_count') {
    return `${options.count} selected`;
  }
  return labels[key] || key;
};

function TargetSelectorHarness({
  clearFieldError,
  initialTargets,
  onTargets,
  sourceLanguageCode = 'en',
}) {
  const [targetLanguageCodes, setTargetLanguageCodes] = React.useState(initialTargets);
  const form = {
    values: { target_lang_codes: targetLanguageCodes },
    clearFieldError,
    setFieldValue: (field, value) => {
      if (field === 'target_lang_codes') setTargetLanguageCodes(value);
    },
  };

  React.useEffect(() => {
    onTargets(targetLanguageCodes);
  }, [onTargets, targetLanguageCodes]);

  return (
    <MantineProvider>
      <LanguageTargetSelector
        form={form}
        languages={languages}
        sourceLanguageCode={sourceLanguageCode}
        t={t}
      />
    </MantineProvider>
  );
}

describe('LanguageTargetSelector', () => {
  it('removes the source language from both choices and restored form state', async () => {
    const onTargets = vi.fn();

    render(
      <TargetSelectorHarness
        clearFieldError={vi.fn()}
        initialTargets={['en', 'fr']}
        onTargets={onTargets}
      />
    );

    expect(screen.queryByRole('button', { name: 'English' })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(onTargets).toHaveBeenLastCalledWith(['fr']);
    });
    expect(screen.getByRole('button', { name: 'Français' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('selects every eligible target without reintroducing the source language', async () => {
    const clearFieldError = vi.fn();
    const onTargets = vi.fn();

    render(
      <TargetSelectorHarness
        clearFieldError={clearFieldError}
        initialTargets={[]}
        onTargets={onTargets}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Choose at least one target');
    fireEvent.click(screen.getByRole('button', { name: 'Select all' }));

    await waitFor(() => {
      expect(onTargets).toHaveBeenLastCalledWith(['fr', 'zh-CN']);
    });
    expect(clearFieldError).toHaveBeenCalledWith('target_lang_codes');
    expect(screen.getByRole('button', { name: 'Français' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '简体中文' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('toggles individual targets and clears the selection', async () => {
    const onTargets = vi.fn();

    render(
      <TargetSelectorHarness
        clearFieldError={vi.fn()}
        initialTargets={[]}
        onTargets={onTargets}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Français' }));
    await waitFor(() => {
      expect(onTargets).toHaveBeenLastCalledWith(['fr']);
    });

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'Clear all' }));
    });
    await waitFor(() => {
      expect(onTargets).toHaveBeenLastCalledWith([]);
    });
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

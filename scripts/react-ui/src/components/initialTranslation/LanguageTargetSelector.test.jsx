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
const allLanguages = {
  ...languages,
  de: { code: 'de', key: 'l_german', name: 'Deutsch' },
  es: { code: 'es', key: 'l_spanish', name: 'Español' },
  pl: { code: 'pl', key: 'l_polish', name: 'Polski' },
  'pt-BR': { code: 'pt-BR', key: 'l_braz_por', name: 'Português do Brasil' },
  ru: { code: 'ru', key: 'l_russian', name: 'Русский' },
  tr: { code: 'tr', key: 'l_turkish', name: 'Türkçe' },
  ja: { code: 'ja', key: 'l_japanese', name: '日本語' },
  ko: { code: 'ko', key: 'l_korean', name: '한국어' },
};

const t = (key, options) => {
  const labels = {
    initial_translation_clear_all: 'Clear all',
    initial_translation_select_all: 'Select all',
    initial_translation_target_none: 'No targets',
    initial_translation_target_required: 'Choose at least one target',
    initial_translation_target_section_title: 'Target languages',
    'mars_pipeline.language_es_spain': 'Spanish (Spain)',
    'mars_pipeline.language_pt_br': 'Portuguese (Brazil)',
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
  gameId,
  supportedLanguageCodes,
  availableLanguages = languages,
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
        languages={availableLanguages}
        gameId={gameId}
        supportedLanguageCodes={supportedLanguageCodes}
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

  it('uses Mars profile languages only and labels Spain and Brazil explicitly', () => {
    render(
      <TargetSelectorHarness
        clearFieldError={vi.fn()}
        initialTargets={[]}
        onTargets={vi.fn()}
        gameId="surviving_mars"
        supportedLanguageCodes={['zh-CN', 'en', 'fr', 'de', 'es', 'pl', 'pt-BR', 'ru', 'tr']}
        availableLanguages={allLanguages}
      />
    );

    expect(screen.getByRole('button', { name: 'Spanish (Spain)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Portuguese (Brazil)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '日本語' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '한국어' })).not.toBeInTheDocument();
  });

  it('removes targets unsupported by the newly selected game profile', async () => {
    const onTargets = vi.fn();
    const props = {
      clearFieldError: vi.fn(),
      initialTargets: ['ja', 'ko', 'fr'],
      onTargets,
      availableLanguages: allLanguages,
    };
    const { rerender } = render(<TargetSelectorHarness {...props} gameId="stellaris" />);
    expect(screen.getByRole('button', { name: '日本語' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '한국어' })).toBeInTheDocument();

    rerender(
      <TargetSelectorHarness
        {...props}
        gameId="surviving_mars"
        supportedLanguageCodes={['zh-CN', 'en', 'fr', 'de', 'es', 'pl', 'pt-BR', 'ru', 'tr']}
      />
    );

    await waitFor(() => {
      expect(onTargets).toHaveBeenLastCalledWith(['fr']);
    });
    expect(screen.queryByRole('button', { name: '日本語' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '한국어' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Français' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps existing Mars selections while its game profile is still loading', async () => {
    const onTargets = vi.fn();
    const props = {
      clearFieldError: vi.fn(),
      initialTargets: ['ja', 'fr'],
      onTargets,
      availableLanguages: allLanguages,
      gameId: 'surviving_mars',
    };
    const { rerender } = render(<TargetSelectorHarness {...props} />);

    expect(screen.getByRole('button', { name: '日本語' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(onTargets).toHaveBeenLastCalledWith(['ja', 'fr']));

    rerender(
      <TargetSelectorHarness
        {...props}
        supportedLanguageCodes={['zh-CN', 'en', 'fr', 'de', 'es', 'pl', 'pt-BR', 'ru', 'tr']}
      />
    );
    await waitFor(() => expect(onTargets).toHaveBeenLastCalledWith(['fr']));
  });

  it('preserves Mars targets while the language catalog loads, then prunes unsupported codes', async () => {
    const onTargets = vi.fn();
    const props = {
      clearFieldError: vi.fn(),
      initialTargets: ['ja', 'fr'],
      onTargets,
      gameId: 'surviving_mars',
      supportedLanguageCodes: ['zh-CN', 'en', 'fr', 'de', 'es', 'pl', 'pt-BR', 'ru', 'tr'],
    };
    const { rerender } = render(
      <TargetSelectorHarness {...props} availableLanguages={{}} />
    );

    await waitFor(() => expect(onTargets).toHaveBeenLastCalledWith(['ja', 'fr']));
    rerender(<TargetSelectorHarness {...props} availableLanguages={allLanguages} />);
    await waitFor(() => expect(onTargets).toHaveBeenLastCalledWith(['fr']));
  });

  it('keeps Japanese and Korean available for other games', () => {
    render(
      <TargetSelectorHarness
        clearFieldError={vi.fn()}
        initialTargets={[]}
        onTargets={vi.fn()}
        gameId="stellaris"
        availableLanguages={allLanguages}
      />
    );

    expect(screen.getByRole('button', { name: '日本語' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '한국어' })).toBeInTheDocument();
  });
});

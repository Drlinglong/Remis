import { describe, expect, it } from 'vitest';

import { formatLocalizedDateTime, getResolvedInterfaceLocale, resolveInterfaceLocale } from './localizedDateTime';

const SUPPORTED_LOCALES = [
  ['en', 'en'],
  ['zh', 'zh-CN'],
  ['ru', 'ru'],
  ['fr', 'fr'],
  ['de', 'de'],
  ['es', 'es'],
  ['ja', 'ja'],
  ['ko', 'ko'],
  ['pl', 'pl'],
  ['pt-BR', 'pt-BR'],
  ['tr', 'tr'],
];

describe('localized date formatting', () => {
  it.each(SUPPORTED_LOCALES)('resolves %s to the supported Intl locale %s', (language, locale) => {
    expect(resolveInterfaceLocale(language)).toBe(locale);
  });

  it.each(['en', 'ru', 'fr', 'de', 'es', 'ko', 'pl', 'pt-BR', 'tr'])(
    'does not produce Chinese date markers for %s',
    (language) => {
      expect(formatLocalizedDateTime('2026-08-01T12:18:00Z', language, {
        dateStyle: 'long',
        timeStyle: 'short',
      })).not.toMatch(/[年月日]/);
    },
  );

  it('keeps Chinese and Japanese date markers valid for their own locales', () => {
    const options = { dateStyle: 'long' };

    expect(formatLocalizedDateTime('2026-08-01T12:18:00Z', 'zh', options)).toMatch(/[年月日]/);
    expect(formatLocalizedDateTime('2026-08-01T12:18:00Z', 'ja', options)).toMatch(/[年月日]/);
  });

  it('normalizes application aliases and prefers the resolved i18n language', () => {
    expect(resolveInterfaceLocale('pt')).toBe('pt-BR');
    expect(resolveInterfaceLocale('pt_BR')).toBe('pt-BR');
    expect(resolveInterfaceLocale('pt-PT')).toBe('pt-BR');
    expect(resolveInterfaceLocale('zh-TW')).toBe('zh-CN');
    expect(getResolvedInterfaceLocale({ language: 'zh', resolvedLanguage: 'ru' })).toBe('ru');
  });

  it('preserves an invalid timestamp as an explicit display value', () => {
    expect(formatLocalizedDateTime('not-a-date', 'ru')).toBe('Invalid Date');
  });
});

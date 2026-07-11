import { describe, expect, it } from 'vitest'
import {
  detectPreferredLocale,
  getInitialLocale,
  normalizeLocale,
  STORAGE_KEY,
  supportedLocales,
} from './locales'

describe('supported website locales', () => {
  it('matches the 11 languages shipped by the Remis desktop app', () => {
    expect(supportedLocales.map(({ code }) => code)).toEqual([
      'en', 'zh', 'ru', 'ja', 'de', 'fr', 'es', 'ko', 'pl', 'pt-BR', 'tr',
    ])
  })

  it.each([
    ['zh-CN', 'zh'],
    ['zh-Hans-CN', 'zh'],
    ['pt-BR', 'pt-BR'],
    ['pt-PT', 'pt-BR'],
    ['de-DE', 'de'],
    ['en-AU', 'en'],
    ['it-IT', null],
  ])('normalizes %s to %s', (input, expected) => {
    expect(normalizeLocale(input)).toBe(expected)
  })
})

describe('browser language negotiation', () => {
  it('uses the first supported browser preference', () => {
    expect(detectPreferredLocale(['it-IT', 'fr-CA', 'en-AU'])).toBe('fr')
  })

  it('falls back to English when no browser preference is supported', () => {
    expect(detectPreferredLocale(['it-IT', 'nl-NL'])).toBe('en')
  })

  it('prioritizes URL, then a manual stored choice, then browser preferences', () => {
    const storage = {
      getItem: (key) => key === STORAGE_KEY ? 'ru' : null,
    }

    expect(getInitialLocale({ search: '?lang=ja', storage, languages: ['fr-FR'] })).toBe('ja')
    expect(getInitialLocale({ storage, languages: ['fr-FR'] })).toBe('ru')
    expect(getInitialLocale({ storage: { getItem: () => null }, languages: ['fr-FR'] })).toBe('fr')
  })
})

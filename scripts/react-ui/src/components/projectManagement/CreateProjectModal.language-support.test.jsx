import { describe, expect, it, vi } from 'vitest';

import {
  getSourceLanguageOptions,
  resolveSupportedSourceLanguage,
} from '../../utils/projectLanguages';

const languages = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: 'Simplified Chinese' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'es', label: 'Spanish' },
  { value: 'pl', label: 'Polish' },
  { value: 'pt-BR', label: 'Portuguese' },
  { value: 'ru', label: 'Russian' },
  { value: 'tr', label: 'Turkish' },
  { value: 'ja', label: 'Japanese' },
  { value: 'ko', label: 'Korean' },
];
const marsCodes = ['zh-CN', 'en', 'fr', 'de', 'es', 'pl', 'pt-BR', 'ru', 'tr'];
const t = (key) => ({
  'mars_pipeline.language_es_spain': 'Spanish (Spain)',
  'mars_pipeline.language_pt_br': 'Portuguese (Brazil)',
}[key] || key);

describe('CreateProjectModal source-language options', () => {
  it('limits Mars CSV source languages to profile support and names Spain and Brazil', () => {
    const options = getSourceLanguageOptions(languages, true, marsCodes, t);

    expect(options.map(({ value }) => value).sort()).toEqual([...marsCodes].sort());
    expect(options.find(({ value }) => value === 'es').label).toBe('Spanish (Spain)');
    expect(options.find(({ value }) => value === 'pt-BR').label).toBe('Portuguese (Brazil)');
    expect(options.some(({ value }) => ['ja', 'ko'].includes(value))).toBe(false);
  });

  it('preserves all global source-language choices for other games', () => {
    expect(getSourceLanguageOptions(languages, false, marsCodes, vi.fn())).toBe(languages);
  });

  it('switches an unsupported source to English when entering the Mars CSV route', () => {
    expect(resolveSupportedSourceLanguage('ja', marsCodes)).toBe('en');
    expect(resolveSupportedSourceLanguage('es', marsCodes)).toBe('es');
    expect(resolveSupportedSourceLanguage('ja')).toBe('en');
  });
});

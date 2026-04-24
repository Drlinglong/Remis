import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const localeFiles = {
  en: path.resolve(__dirname, '../locales/en/translation.json'),
  ru: path.resolve(__dirname, '../locales/ru/translation.json'),
  zh: path.resolve(__dirname, '../locales/zh/translation.json'),
};

const loadLocale = (filePath) => JSON.parse(readFileSync(filePath, 'utf8'));

const flattenKeys = (value, prefix = '') => {
  if (Array.isArray(value) || value === null || typeof value !== 'object') {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value).flatMap(([key, nestedValue]) => {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    return flattenKeys(nestedValue, nextPrefix);
  });
};

const flattenEntries = (value, prefix = '') => {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => flattenEntries(item, `${prefix}[${index}]`));
  }

  if (value !== null && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, nestedValue]) => {
      const nextPrefix = prefix ? `${prefix}.${key}` : key;
      return flattenEntries(nestedValue, nextPrefix);
    });
  }

  return prefix ? [[prefix, value]] : [];
};

describe('locale consistency', () => {
  it('keeps all translation keys aligned across all locales', () => {
    const localeKeySets = Object.fromEntries(
      Object.entries(localeFiles).map(([locale, filePath]) => {
        const localeData = loadLocale(filePath);
        return [locale, new Set(flattenKeys(localeData))];
      }),
    );

    const allKeys = new Set(
      Object.values(localeKeySets).flatMap((keySet) => Array.from(keySet)),
    );

    const mismatches = Object.entries(localeKeySets).flatMap(([locale, keySet]) => {
      const missing = Array.from(allKeys).filter((key) => !keySet.has(key));
      return missing.map((key) => `${locale} missing: ${key}`);
    });

    expect(mismatches, mismatches.join('\n')).toEqual([]);
  });

  it('keeps common browse localized outside English', () => {
    const enLocale = loadLocale(localeFiles.en);
    const ruLocale = loadLocale(localeFiles.ru);
    const zhLocale = loadLocale(localeFiles.zh);

    expect(enLocale.common.browse).toBe('Browse');
    expect(ruLocale.common.browse).not.toBe(enLocale.common.browse);
    expect(zhLocale.common.browse).not.toBe(enLocale.common.browse);
  });

  it('does not leave locale strings as pure question-mark placeholders', () => {
    const placeholderPattern = /^\?{3,}$/;
    const longQuestionRunPattern = /\?{8,}/;

    const offenders = Object.entries(localeFiles).flatMap(([locale, filePath]) => {
      const localeData = loadLocale(filePath);
      return flattenEntries(localeData)
        .filter(([, value]) => typeof value === 'string')
        .filter(([, value]) => placeholderPattern.test(value.trim()) || longQuestionRunPattern.test(value))
        .map(([key, value]) => `${locale}.${key} => ${JSON.stringify(value)}`);
    });

    expect(offenders, offenders.join('\n')).toEqual([]);
  });

  it('does not leave critical zh/ru UI strings as placeholder question marks', () => {
    const ruLocale = loadLocale(localeFiles.ru);
    const zhLocale = loadLocale(localeFiles.zh);

    const criticalValues = [
      zhLocale.tutorial.agent_workshop.scan.desc,
      zhLocale.translation_page.translation_limit_auto,
      zhLocale.translation_page.translation_batch_size,
      zhLocale.translation_page.resume_detail_none,
      zhLocale.translation_page.embedded_workshop_following_summary,
      zhLocale.incremental_translation.batch_size_limit_desc,
      ruLocale.tutorial.agent_workshop.scan.desc,
      ruLocale.translation_page.translation_limit_auto,
      ruLocale.translation_page.translation_batch_size,
      ruLocale.translation_page.resume_detail_none,
      ruLocale.translation_page.embedded_workshop_following_summary,
      ruLocale.incremental_translation.batch_size_limit_desc,
    ];

    criticalValues.forEach((value) => {
      expect(value).not.toMatch(/^\?+$/);
      expect(value).not.toMatch(/^\?[\?\s:{}\/()-]*$/);
      expect(value).toMatch(/[^\x00-\x7F]/);
    });
  });
});

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
});

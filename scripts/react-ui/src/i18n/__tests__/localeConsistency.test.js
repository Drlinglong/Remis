import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const localeFiles = {
  de: path.resolve(__dirname, '../locales/de/translation.json'),
  en: path.resolve(__dirname, '../locales/en/translation.json'),
  es: path.resolve(__dirname, '../locales/es/translation.json'),
  fr: path.resolve(__dirname, '../locales/fr/translation.json'),
  ja: path.resolve(__dirname, '../locales/ja/translation.json'),
  ko: path.resolve(__dirname, '../locales/ko/translation.json'),
  pl: path.resolve(__dirname, '../locales/pl/translation.json'),
  'pt-BR': path.resolve(__dirname, '../locales/pt-BR/translation.json'),
  ru: path.resolve(__dirname, '../locales/ru/translation.json'),
  tr: path.resolve(__dirname, '../locales/tr/translation.json'),
  zh: path.resolve(__dirname, '../locales/zh/translation.json'),
};

const loadLocale = (filePath) => JSON.parse(readFileSync(filePath, 'utf8'));

const steamWorkshopRoot = path.resolve(__dirname, '../../components/steamWorkshop');
const steamWorkshopUiSources = readdirSync(steamWorkshopRoot, { recursive: true })
  .filter((relativePath) => /\.[jt]sx?$/.test(relativePath))
  .filter((relativePath) => !/\.(test|regression)\.[jt]sx?$/.test(relativePath))
  .map((relativePath) => path.resolve(steamWorkshopRoot, relativePath))
  // This module contains locale-name data (for example, the native Chinese
  // name of Chinese), not rendered UI copy. Keep this exception exact.
  .filter((filePath) => !filePath.endsWith(`${path.sep}coverEditorAssets.js`))
  .concat([
    path.resolve(__dirname, '../../pages/SteamWorkshopPage.jsx'),
    path.resolve(__dirname, '../../components/tools/ThumbnailGenerator.jsx'),
    path.resolve(__dirname, '../../components/tools/WorkshopGenerator.jsx'),
  ]);

const steamWorkshopKeyPattern = /t\(\s*['"]((?:steam_workshop|tutorial\.steam_workshop)\.[\w.]+)/g;
const referenceLibraryRoot = path.resolve(__dirname, '../../components/settings');
const referenceLibraryUiSources = readdirSync(referenceLibraryRoot)
  .filter((relativePath) => /^ReferenceLibrary.*\.jsx$/.test(relativePath))
  .map((relativePath) => path.resolve(referenceLibraryRoot, relativePath))
  .concat(path.resolve(
    __dirname,
    '../../components/initialTranslation/ReferenceLibraryAvailabilityNotice.jsx',
  ));
const referenceLibraryKeyPattern = /['"]((?:settings_reference_[\w]+|common\.[\w.]+|button_close|cancel))['"]/g;

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

const releaseDuplicateValueAllowlist = new Set([
  'page_title_cicd',
  'homepage_action_card_new_project_icon',
  'homepage_action_card_update_project_icon',
  'settings_api_label_url',
  'form_placeholder_folder_path',
  'api_desc_minimax',
  'project_management.details.id',
  'incremental_translation.warning_validation_prefix',
  // "Format Repair" is the fixed product identity outside Chinese. Keep these
  // exact keys exempt instead of reopening a broad Agent Workshop pattern.
  'page_title_agent_workshop',
  'agent_workshop.title',
  'task_center.kind.agent_workshop',
  'task_center.kind.agent_workshop_batch',
  'task_center.kind.repair',
  // BBCode is a protected technical term and can legitimately remain the
  // same in otherwise natural localized publishing copy.
  'steam_workshop.bbcode',
]);

const releaseDuplicateValueAllowlistPatterns = [
  /^game_name_/,
  /^theme_/,
  /^app_title$/,
  // Short standardized effort labels (for example, "low" or "max") can
  // legitimately have the same spelling in otherwise distinct locales.
  /^api_reasoning_preset_/,
];

const isAllowedReleaseDuplicateKey = (key) => (
  releaseDuplicateValueAllowlist.has(key)
  || releaseDuplicateValueAllowlistPatterns.some((pattern) => pattern.test(key))
);

const steamWorkshopExactFallbackAllowlist = new Set([
  // These values are structural or protected terms, not a source-language
  // sentence. Every other Steam key must differ from both English and Chinese.
  'steam_workshop.asset_version',
  'steam_workshop.bbcode',
  'steam_workshop.workshop_id_label',
]);

const isAllowedSteamWorkshopFallback = (locale, key) => (
  steamWorkshopExactFallbackAllowlist.has(key)
  || (locale === 'ja' && key === 'steam_workshop.save')
);

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

  it('does not allow the Steam publishing UI to bypass release locale entries', () => {
    const localeEntries = Object.fromEntries(
      Object.entries(localeFiles).map(([locale, filePath]) => [
        locale,
        Object.fromEntries(flattenEntries(loadLocale(filePath))),
      ]),
    );
    const sources = steamWorkshopUiSources.map((filePath) => [
      filePath,
      readFileSync(filePath, 'utf8'),
    ]);
    const hardcodedChinese = sources.flatMap(([filePath, source]) => (
      source.match(/[\u4e00-\u9fff]/g)
        ? [`${path.relative(__dirname, filePath)} contains hard-coded Chinese UI text`]
        : []
    ));
    const referencedKeys = new Set(
      sources.flatMap(([, source]) => Array.from(source.matchAll(steamWorkshopKeyPattern), ([, key]) => key)),
    );
    const missing = Array.from(referencedKeys).flatMap((key) => (
      Object.entries(localeEntries)
        .filter(([, entries]) => typeof entries[key] !== 'string' || entries[key].trim() === '')
        .map(([locale]) => `${locale}.${key} missing from release locale`)
    ));
    const copiedChinese = Array.from(referencedKeys).flatMap((key) => (
      Object.entries(localeEntries)
        .filter(([locale, entries]) => (
          locale !== 'zh'
          && entries[key] === localeEntries.zh[key]
          && !isAllowedSteamWorkshopFallback(locale, key)
        ))
        .map(([locale]) => `${locale}.${key} still mirrors Chinese`)
    ));
    const copiedEnglish = Array.from(referencedKeys).flatMap((key) => (
      Object.entries(localeEntries)
        .filter(([locale, entries]) => (
          locale !== 'en'
          && locale !== 'zh'
          && entries[key] === localeEntries.en[key]
          && !isAllowedSteamWorkshopFallback(locale, key)
        ))
        .map(([locale]) => `${locale}.${key} still mirrors English`)
    ));

    expect(hardcodedChinese, hardcodedChinese.join('\n')).toEqual([]);
    expect(missing, missing.join('\n')).toEqual([]);
    expect(copiedChinese, copiedChinese.join('\n')).toEqual([]);
    expect(copiedEnglish, copiedEnglish.join('\n')).toEqual([]);
  });

  it('does not allow the reference library UI to reference missing locale entries', () => {
    const localeEntries = Object.fromEntries(
      Object.entries(localeFiles).map(([locale, filePath]) => [
        locale,
        Object.fromEntries(flattenEntries(loadLocale(filePath))),
      ]),
    );
    const referencedKeys = new Set(referenceLibraryUiSources.flatMap((filePath) => (
      Array.from(
        readFileSync(filePath, 'utf8').matchAll(referenceLibraryKeyPattern),
        ([, key]) => key,
      )
    )));
    const missing = Array.from(referencedKeys).flatMap((key) => (
      Object.entries(localeEntries)
        .filter(([, entries]) => typeof entries[key] !== 'string' || entries[key].trim() === '')
        .map(([locale]) => `${locale}.${key} missing from release locale`)
    ));

    expect(missing, missing.join('\n')).toEqual([]);
  });

  it('keeps every release locale key populated and avoids identical values across all locales', () => {
    const localeEntries = Object.fromEntries(
      Object.entries(localeFiles).map(([locale, filePath]) => [
        locale,
        Object.fromEntries(flattenEntries(loadLocale(filePath))),
      ]),
    );

    const allKeys = Object.keys(localeEntries.en);
    const offenders = allKeys.flatMap((key) => {
      const values = Object.entries(localeEntries).map(([locale, entries]) => [
        locale,
        entries[key],
      ]);
      const missing = values
        .filter(([, value]) => typeof value !== 'string' || value.trim() === '')
        .map(([locale]) => `${locale}.${key} missing or empty`);
      if (missing.length > 0) {
        return missing;
      }

      if (isAllowedReleaseDuplicateKey(key)) {
        return [];
      }

      const seenValues = new Map();
      const duplicatePairs = [];
      values.forEach(([locale, value]) => {
        const normalizedValue = value.trim();
        if (seenValues.has(normalizedValue)) {
          duplicatePairs.push(
            `${key} duplicated in ${seenValues.get(normalizedValue)} and ${locale}: ${JSON.stringify(normalizedValue)}`,
          );
        } else {
          seenValues.set(normalizedValue, locale);
        }
      });

      if (duplicatePairs.length > 0) {
        return duplicatePairs;
      }
      return [];
    });

    expect(offenders, offenders.join('\n')).toEqual([]);
  });

  it('does not ship project tracking strings as English fallbacks outside English', () => {
    const enEntries = Object.fromEntries(flattenEntries(loadLocale(localeFiles.en)));
    const projectTrackingKeys = Object.keys(enEntries).filter((key) => (
      key.startsWith('project_tracking.') || key.startsWith('tutorial.project_tracking.')
    ));

    const offenders = Object.entries(localeFiles)
      .filter(([locale]) => locale !== 'en')
      .flatMap(([locale, filePath]) => {
        const entries = Object.fromEntries(flattenEntries(loadLocale(filePath)));
        return projectTrackingKeys
          .filter((key) => entries[key] === enEntries[key])
          .map((key) => `${locale}.${key} still mirrors English`);
      });

    expect(offenders, offenders.join('\n')).toEqual([]);
  });

  it('keeps common browse localized outside English', () => {
    const enLocale = loadLocale(localeFiles.en);
    const ruLocale = loadLocale(localeFiles.ru);
    const zhLocale = loadLocale(localeFiles.zh);

    expect(enLocale.common.browse).toBe('Browse');
    expect(ruLocale.common.browse).not.toBe(enLocale.common.browse);
    expect(zhLocale.common.browse).not.toBe(enLocale.common.browse);
  });

  it('localizes the Format Repair menu label and keeps the internal Remis Agent distinct', () => {
    const enLocale = loadLocale(localeFiles.en);
    const zhLocale = loadLocale(localeFiles.zh);
    const legacyProductNamePattern = (
      /Agent[- ]Workshop|Smart Workshop|workshop|智能工坊|智能工作坊|工坊|Werkstatt|taller|atelier|ワークショップ|워크숍|작업실|warsztat|oficina|мастерск|atölye/i
    );
    const productKeyPattern = (
      /^(page_title_agent_workshop|task_center\.kind\.(agent_workshop|agent_workshop_batch|repair)|agent_workshop\.|project_validation\.|tutorial\.agent_workshop\.|tutorial\.project_management\.validation_workshop\.|tutorial\.incremental_translation\.workshop\.|translation_page\.embedded_workshop_|incremental_translation\.(embedded_workshop_|telemetry_(workshop_export|embedded_workshop)|validation_issue_summary_)|report_format_repair_)/
    );

    expect(enLocale.page_title_agent_workshop).toBe('Format Repair');
    expect(enLocale.agent_workshop.title).toBe('Format Repair');
    expect(enLocale.agent_workshop.description).toBe(
      'Check and batch-repair format issues in localization files.',
    );
    expect(enLocale.task_center.creator.remis_agent).toBe('Remis Agent');
    expect(enLocale.task_center.creator.remis_agent).not.toBe(enLocale.page_title_agent_workshop);

    expect(zhLocale.page_title_agent_workshop).toBe('格式修复台');
    expect(zhLocale.agent_workshop.title).toBe('格式修复台');
    expect(zhLocale.agent_workshop.description).toBe(
      '检查并批量修复本地化文件中的格式问题。',
    );
    expect(zhLocale.task_center.creator.remis_agent).not.toBe(zhLocale.page_title_agent_workshop);

    const offenders = Object.entries(localeFiles).flatMap(([locale, filePath]) => (
      flattenEntries(loadLocale(filePath))
        .filter(([key, value]) => productKeyPattern.test(key) && typeof value === 'string')
        .filter(([, value]) => legacyProductNamePattern.test(
          value.replaceAll('workshop_issues.json', ''),
        ))
        .map(([key, value]) => `${locale}.${key}: ${JSON.stringify(value)}`)
    ));
    expect(offenders, offenders.join('\n')).toEqual([]);

    const localizedMenuLabels = {
      de: 'Formatreparatur',
      en: 'Format Repair',
      es: 'Reparación de formato',
      fr: 'Réparation du format',
      ja: 'フォーマット修復',
      ko: '형식 복구',
      pl: 'Naprawa formatowania',
      'pt-BR': 'Reparo de formatação',
      ru: 'Исправление формата',
      tr: 'Biçim Onarımı',
      zh: '格式修复台',
    };
    Object.entries(localeFiles).forEach(([locale, filePath]) => {
      const localeData = loadLocale(filePath);
      const productName = locale === 'zh' ? '格式修复台' : 'Format Repair';
      expect(localeData.page_title_agent_workshop).toBe(localizedMenuLabels[locale]);
      expect(localeData.agent_workshop.title).toBe(productName);
      expect(localeData.task_center.kind.agent_workshop).toBe(
        productName,
      );
      expect(localeData.task_center.kind.agent_workshop_batch).toBe(
        locale === 'zh' ? '格式修复批次' : 'Format Repair batch',
      );
      expect(localeData.task_center.kind.repair).toBe(
        locale === 'zh' ? '格式修复' : 'Format repair',
      );
      expect(localeData.incremental_translation.telemetry_workshop_export).toContain(productName);
      expect(localeData.incremental_translation.telemetry_embedded_workshop).toContain(productName);
      expect(localeData.incremental_translation.validation_issue_summary_title).toContain(productName);
    });
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
      expect(value).not.toMatch(/^\?[?\s:{}/()-]*$/);
      // eslint-disable-next-line no-control-regex
      expect(value).toMatch(/[^\x00-\x7F]/);
    });
  });

  it('localizes recent deploy and warning strings outside English', () => {
    const enLocale = loadLocale(localeFiles.en);
    const enEntries = Object.fromEntries(flattenEntries(enLocale));
    const keysThatMustNotMirrorEnglish = [
      'deploy_loading_target_path',
      'deploy_error_load_info',
      'translation_completed_with_warnings',
      'translation_partial_fail_summary',
      'error_cannot_open_folder',
      'error_output_folder_not_available',
      'partial_failure_title',
      'partial_failure_review_msg',
    ];

    const offenders = Object.entries(localeFiles)
      .filter(([locale]) => locale !== 'en')
      .flatMap(([locale, filePath]) => {
        const entries = Object.fromEntries(flattenEntries(loadLocale(filePath)));
        return keysThatMustNotMirrorEnglish
          .filter((key) => entries[key] === enEntries[key])
          .map((key) => `${locale}.${key} still mirrors English`);
      });

    expect(offenders, offenders.join('\n')).toEqual([]);
  });

  it('does not leave known Chinese UI blocks in English', () => {
    const zhEntries = Object.fromEntries(flattenEntries(loadLocale(localeFiles.zh)));
    const keysThatMustContainChinese = [
      'project_management.delete_note_confirm_content',
      'translation_page.resume_detail_empty',
      'incremental_translation.resume_detail_title',
      'incremental_translation.resume_detail_completed',
      'incremental_translation.embedded_workshop_enabled',
      'incremental_translation.embedded_workshop_settings',
      'thumbnail_generator.description',
      'thumbnail_generator.drag_hint',
      'proofreading.target_language',
      'proofreading.modal.title',
      'proofreading.modal.content_1',
      'proofreading.modal.content_2',
      'proofreading.modal.button_cancel',
    ];

    const offenders = keysThatMustContainChinese
      .filter((key) => !/[\u4e00-\u9fff]/.test(zhEntries[key] || ''))
      .map((key) => `${key}: ${JSON.stringify(zhEntries[key])}`);

    expect(offenders, offenders.join('\n')).toEqual([]);
  });
});

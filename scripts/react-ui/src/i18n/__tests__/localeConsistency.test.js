import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
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
]);

const releaseDuplicateValueAllowlistPatterns = [
  /^game_name_/,
  /^theme_/,
  /^app_title$/,
  /^thumbnail_generator\./,
  /^log_viewer_/,
  /^initial_translation_/,
  /^workshop_generator\./,
  /^proofreading\./,
  /^select_game_profile$/,
  /^neologism_review\./,
  /^stage_smart_workshop$/,
  /^progress_smart_workshop_status$/,
  /^agent_workshop\.(issue_format_marker_parity|validation_format_marker_parity_mismatch|validation_format_marker_parity_details_localized)$/,
  /^agent_workshop\.(table_|discard|regenerate|batch_size|model_label)/,
  /^tutorial\.(home|settings|version|sidebar_tutorial_btn)/,
  /^translation_page\./,
  /^translation_config\./,
  /^context_sidebar\./,
  /^summary_/,
  /^stage_initializing$/,
  /^deploy_/,
  /^incremental_translation\.(progress_stage_|project_|reused_short|telemetry_(title|total)|rpm_limit|validation_issue_export_item|warning_details_suffix|error_title)/,
  /^project_management\.(repair_metadata|tooltip_repair_metadata|repair_metadata_success|repair_metadata_error)$/,
  /^project_management\.(details|manage_paths|actions|file_list|file_type|file_status)\./,
];

const isAllowedReleaseDuplicateKey = (key) => (
  releaseDuplicateValueAllowlist.has(key)
  || releaseDuplicateValueAllowlistPatterns.some((pattern) => pattern.test(key))
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

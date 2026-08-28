import { describe, expect, it } from 'vitest';

import {
  buildIncrementalUpdatePayload,
  getArchivedTargetLanguages,
  normalizeArrayPayload,
} from './incrementalTranslationPayload';

describe('incrementalTranslationPayload', () => {
  it('normalizes array API payloads from known wrapper keys', () => {
    expect(normalizeArrayPayload([{ id: 1 }])).toEqual([{ id: 1 }]);
    expect(normalizeArrayPayload({ items: [{ id: 2 }] }, ['items'])).toEqual([{ id: 2 }]);
    expect(normalizeArrayPayload({ data: [{ id: 3 }] }, ['items', 'data'])).toEqual([{ id: 3 }]);
    expect(normalizeArrayPayload(null, ['items'])).toEqual([]);
  });

  it('extracts archived target languages from supported archive shapes', () => {
    expect(getArchivedTargetLanguages({ archived_languages: ['zh-CN', null, 'fr'] })).toEqual(['zh-CN', 'fr']);
    expect(getArchivedTargetLanguages({ target_languages: ['de', undefined] })).toEqual(['de']);
    expect(getArchivedTargetLanguages({ target_language: 'ja' })).toEqual(['ja']);
    expect(getArchivedTargetLanguages(null)).toEqual([]);
  });

  it('builds incremental update payloads with primary workshop settings', () => {
    expect(buildIncrementalUpdatePayload({
      batchSizeLimit: '',
      concurrencyLimit: '10',
      customSourcePath: 'J:/mod',
      dryRun: true,
      embeddedWorkshopBatchSize: '5',
      embeddedWorkshopConcurrency: '2',
      embeddedWorkshopEnabled: true,
      embeddedWorkshopFollowPrimary: true,
      embeddedWorkshopModel: 'secondary-model',
      embeddedWorkshopProvider: 'secondary-provider',
      embeddedWorkshopRpm: '20',
      projectId: 7,
      referenceLocalizationPath: 'J:/vanilla/localization',
      referenceReuseExcludedEntries: [{
        file_path: 'localization/english/countries.yml',
        key: 'TRK:0',
        source_text: 'Turkana',
        target_lang_code: 'zh-CN',
      }],
      referenceReuseEnabled: true,
      rpmLimit: '40',
      selectedModel: 'primary-model',
      selectedProvider: 'gemini',
      targetLangCodes: ['zh-CN'],
      useResume: false,
    })).toEqual({
      project_id: 7,
      target_lang_codes: ['zh-CN'],
      dry_run: true,
      api_provider: 'gemini',
      model: 'primary-model',
      batch_size_limit: null,
      concurrency_limit: 10,
      rpm_limit: 40,
      custom_source_path: 'J:/mod',
      use_resume: false,
      reference_reuse: {
        enabled: true,
        localization_path: 'J:/vanilla/localization',
        excluded_entries: [{
          file_path: 'localization/english/countries.yml',
          key: 'TRK:0',
          source_text: 'Turkana',
          target_lang_code: 'zh-CN',
        }],
      },
      embedded_workshop: {
        enabled: true,
        follow_primary_settings: true,
        api_provider: null,
        api_model: null,
        batch_size_limit: null,
        concurrency_limit: 10,
        rpm_limit: 40,
      },
    });
  });

  it('builds incremental update payloads with independent workshop settings', () => {
    const payload = buildIncrementalUpdatePayload({
      batchSizeLimit: '12',
      concurrencyLimit: '10',
      customSourcePath: 'J:/mod',
      dryRun: false,
      embeddedWorkshopBatchSize: '5',
      embeddedWorkshopConcurrency: '2',
      embeddedWorkshopEnabled: true,
      embeddedWorkshopFollowPrimary: false,
      embeddedWorkshopModel: 'secondary-model',
      embeddedWorkshopProvider: 'ollama',
      embeddedWorkshopRpm: '20',
      projectId: 7,
      referenceLocalizationPath: '',
      referenceReuseEnabled: false,
      rpmLimit: '40',
      selectedModel: 'primary-model',
      selectedProvider: 'gemini',
      targetLangCodes: ['zh-CN'],
      useResume: true,
    });

    expect(payload.embedded_workshop).toEqual({
      enabled: true,
      follow_primary_settings: false,
      api_provider: 'ollama',
      api_model: 'secondary-model',
      batch_size_limit: 5,
      concurrency_limit: 2,
      rpm_limit: 20,
    });
    expect(payload.batch_size_limit).toBe(12);
    expect(payload.dry_run).toBe(false);
    expect(payload.use_resume).toBe(true);
    expect(payload.reference_reuse).toEqual({
      enabled: false,
      localization_path: '',
      excluded_entries: [],
    });
  });
});

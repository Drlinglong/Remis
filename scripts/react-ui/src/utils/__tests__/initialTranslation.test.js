import { describe, expect, it } from 'vitest';

import {
  buildTranslationDetails,
  buildTranslationPayload,
  resolvePreferredModel,
} from '../initialTranslation';

describe('initialTranslation utils', () => {
  it('shows the actual custom target and disguise language in the completion summary', () => {
    const details = buildTranslationDetails({
      source_lang_code: 'en',
      target_lang_codes: [],
      api_provider: 'openai',
      model_name: 'gpt-4.1-mini',
      english_disguise: true,
      custom_name: 'Vietnamese',
      custom_key: 'l_english',
    }, { value: 'proj-1', label: 'TFR', game_id: 'hoi4' }, {
      english: { code: 'en', key: 'l_english', name: 'English' },
    });

    expect(details.targetLangs).toEqual(['Vietnamese (disguised as English)']);
  });

  it('builds embedded workshop payload with primary settings stripped to nulls', () => {
    const payload = buildTranslationPayload({
      source_lang_code: 'en',
      target_lang_codes: ['zh-CN', 'ru'],
      api_provider: 'gemini',
      model_name: 'gemini-pro',
      mod_context: 'ship it',
      selected_glossary_ids: ['2', '3'],
      translation_context_mode: 'archive',
      clean_source: false,
      use_resume: true,
      reference_reuse_enabled: true,
      reference_localization_path: 'J:/vanilla/localization',
      reference_reuse_excluded_entries: [],
      translation_batch_size_limit: '20',
      translation_concurrency_limit: '4',
      translation_rpm_limit: '60',
      embedded_workshop_enabled: true,
      embedded_workshop_follow_primary_settings: true,
      embedded_workshop_api_provider: 'openai',
      embedded_workshop_api_model: 'gpt-4.1',
      embedded_workshop_batch_size_limit: '15',
      embedded_workshop_concurrency_limit: '2',
      embedded_workshop_rpm_limit: '80',
      english_disguise: false,
    }, 'proj-1');

    expect(payload).toEqual({
      project_id: 'proj-1',
      source_lang_code: 'en',
      target_lang_codes: ['zh-CN', 'ru'],
      api_provider: 'gemini',
      model: 'gemini-pro',
      mod_context: 'ship it',
      selected_glossary_ids: ['2', '3'],
      translation_context_mode: 'archive',
      use_main_glossary: true,
      use_project_context: true,
      clean_source: false,
      use_resume: true,
      reference_reuse: {
        enabled: true,
        localization_path: 'J:/vanilla/localization',
        excluded_entries: [],
      },
      batch_size_limit: 20,
      concurrency_limit: 4,
      rpm_limit: 60,
      embedded_workshop: {
        enabled: true,
        follow_primary_settings: true,
        api_provider: null,
        api_model: null,
        batch_size_limit: 20,
        concurrency_limit: 4,
        rpm_limit: 60,
      },
    });
  });

  it.each([
    ['none', [], false, false],
    ['glossaries', [2], true, false],
    ['archive', [2], true, true],
  ])('maps %s to one deterministic backend resource policy', (
    mode,
    glossaryIds,
    useMainGlossary,
    useProjectContext,
  ) => {
    const payload = buildTranslationPayload({
      source_lang_code: 'en',
      target_lang_codes: ['zh-CN'],
      api_provider: 'local',
      model_name: 'local-model',
      mod_context: '',
      selected_glossary_ids: [2],
      translation_context_mode: mode,
      clean_source: false,
      use_resume: false,
      translation_batch_size_limit: '',
      translation_concurrency_limit: '',
      translation_rpm_limit: '40',
      embedded_workshop_enabled: false,
      embedded_workshop_follow_primary_settings: true,
      english_disguise: false,
    }, 'proj-1');

    expect(payload).toMatchObject({
      translation_context_mode: mode,
      selected_glossary_ids: glossaryIds,
      use_main_glossary: useMainGlossary,
      use_project_context: useProjectContext,
    });
  });

  it('builds custom language payload and keeps explicit embedded workshop settings', () => {
    const payload = buildTranslationPayload({
      source_lang_code: 'en',
      target_lang_codes: [],
      api_provider: 'openai',
      model_name: 'gpt-4.1-mini',
      mod_context: '',
      selected_glossary_ids: [],
      use_main_glossary: false,
      clean_source: true,
      use_resume: false,
      translation_batch_size_limit: '',
      translation_concurrency_limit: '',
      translation_rpm_limit: '40',
      embedded_workshop_enabled: true,
      embedded_workshop_follow_primary_settings: false,
      embedded_workshop_api_provider: 'gemini',
      embedded_workshop_api_model: 'gemini-flash',
      embedded_workshop_batch_size_limit: '',
      embedded_workshop_concurrency_limit: '',
      embedded_workshop_rpm_limit: '',
      english_disguise: true,
      custom_name: 'Custom English',
      custom_key: 'l_english',
      custom_prefix: 'Custom-',
    }, 'proj-1');

    expect(payload.target_lang_codes).toEqual(['custom']);
    expect(payload.custom_lang_config).toEqual({
      name: 'Custom English',
      code: 'custom',
      key: 'l_english',
      folder_prefix: 'Custom-',
    });
    expect(payload.embedded_workshop).toEqual({
      enabled: true,
      follow_primary_settings: false,
      api_provider: 'gemini',
      api_model: 'gemini-flash',
      batch_size_limit: 10,
      concurrency_limit: 1,
      rpm_limit: 40,
    });
  });

  it('uses the selected project source language and filters matching targets', () => {
    const payload = buildTranslationPayload({
      source_lang_code: 'en',
      target_lang_codes: ['en', 'ja'],
      api_provider: 'local',
      model_name: 'local-model',
      mod_context: '',
      selected_glossary_ids: [],
      use_main_glossary: true,
      clean_source: false,
      use_resume: false,
      translation_batch_size_limit: '',
      translation_concurrency_limit: '',
      translation_rpm_limit: '40',
      embedded_workshop_enabled: true,
      embedded_workshop_follow_primary_settings: true,
      embedded_workshop_api_provider: '',
      embedded_workshop_api_model: '',
      embedded_workshop_batch_size_limit: '',
      embedded_workshop_concurrency_limit: '',
      embedded_workshop_rpm_limit: '',
      english_disguise: false,
    }, 'proj-1', { source_language: 'zh-CN' });

    expect(payload.source_lang_code).toBe('zh-CN');
    expect(payload.target_lang_codes).toEqual(['en', 'ja']);
  });

  it('removes the project source language from target languages before starting', () => {
    const payload = buildTranslationPayload({
      source_lang_code: 'en',
      target_lang_codes: ['zh-CN', 'en'],
      api_provider: 'local',
      model_name: 'local-model',
      mod_context: '',
      selected_glossary_ids: [],
      use_main_glossary: true,
      clean_source: false,
      use_resume: false,
      translation_batch_size_limit: '',
      translation_concurrency_limit: '',
      translation_rpm_limit: '40',
      embedded_workshop_enabled: true,
      embedded_workshop_follow_primary_settings: true,
      embedded_workshop_api_provider: '',
      embedded_workshop_api_model: '',
      embedded_workshop_batch_size_limit: '',
      embedded_workshop_concurrency_limit: '',
      embedded_workshop_rpm_limit: '',
      english_disguise: false,
    }, 'proj-1', { source_language: 'zh-CN' });

    expect(payload.source_lang_code).toBe('zh-CN');
    expect(payload.target_lang_codes).toEqual(['en']);
  });

  it('prefers the provider selected model when the current model is no longer valid', () => {
    const nextModel = resolvePreferredModel(
      [
        { value: 'gpt-4.1-mini', label: 'gpt-4.1-mini' },
        { value: 'gpt-4.1', label: 'gpt-4.1' },
      ],
      'gemini-pro',
      'gpt-4.1-mini',
    );

    expect(nextModel).toBe('gpt-4.1-mini');
  });
});

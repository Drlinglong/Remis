import { describe, expect, it } from 'vitest';

import {
  buildTranslationPayload,
  resolvePreferredModel,
} from '../initialTranslation';

describe('initialTranslation utils', () => {
  it('builds embedded workshop payload with primary settings stripped to nulls', () => {
    const payload = buildTranslationPayload({
      source_lang_code: 'en',
      target_lang_codes: ['zh-CN', 'ru'],
      api_provider: 'gemini',
      model_name: 'gemini-pro',
      mod_context: 'ship it',
      selected_glossary_ids: ['2', '3'],
      use_main_glossary: true,
      clean_source: false,
      use_resume: true,
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
      use_main_glossary: true,
      clean_source: false,
      use_resume: true,
      batch_size_limit: 20,
      concurrency_limit: 4,
      rpm_limit: 60,
      embedded_workshop: {
        enabled: true,
        follow_primary_settings: true,
        api_provider: null,
        api_model: null,
        batch_size_limit: 15,
        concurrency_limit: 2,
        rpm_limit: 80,
      },
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

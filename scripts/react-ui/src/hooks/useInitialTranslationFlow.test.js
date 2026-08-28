import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../utils/api';
import translationService from '../services/translationService';
import { useInitialTranslationFlow } from './useInitialTranslationFlow';

vi.mock('../utils/api', () => ({ default: { post: vi.fn(), delete: vi.fn() } }));
vi.mock('../services/translationService', () => ({
  default: { getReferenceLibraryStatus: vi.fn() },
}));
vi.mock('../services/notificationService', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

const values = {
  api_provider: 'gemini',
  clean_source: false,
  embedded_workshop_enabled: false,
  embedded_workshop_follow_primary_settings: true,
  english_disguise: false,
  model_name: 'test-model',
  mod_context: '',
  reference_localization_path: '',
  reference_reuse_enabled: true,
  reference_reuse_excluded_entries: [],
  selected_glossary_ids: [],
  source_lang_code: 'en',
  target_lang_codes: ['zh-CN'],
  use_main_glossary: true,
  use_resume: false,
};

describe('useInitialTranslationFlow reference gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    translationService.getReferenceLibraryStatus.mockResolvedValue({
      data: { libraries: [{ game_id: 'victoria3', available: false }] },
    });
    api.post.mockResolvedValue({ data: { task_id: 'task-initial' } });
  });

  it('prompts on a missing library and disables reuse when the user continues', async () => {
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [{ code: 'en', name: 'English' }, { code: 'zh-CN', name: 'Chinese' }] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'demo',
      setActive: vi.fn(),
      setIsProcessing: vi.fn(),
      setStatus: vi.fn(),
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
    }));

    await act(() => result.current.handleStartClick(values));
    expect(result.current.referencePromptOpen).toBe(true);
    expect(api.post).not.toHaveBeenCalledWith('/api/translate/start', expect.anything());

    await act(() => result.current.continueWithoutReference());
    expect(api.post).toHaveBeenCalledWith(
      '/api/translate/start',
      expect.objectContaining({ reference_reuse: expect.objectContaining({ enabled: false }) }),
    );
  });
});

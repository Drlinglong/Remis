import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../utils/api';
import translationService from '../services/translationService';
import { useInitialTranslationFlow } from './useInitialTranslationFlow';

vi.mock('../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../services/translationService', () => ({
  default: { getReferenceLibraryStatus: vi.fn() },
}));
vi.mock('../services/notificationService', () => ({
  default: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
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
    api.get.mockResolvedValue({ data: { checkpoint: null, allowed_actions: [] } });
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

  it('returns to configuration instead of staying on Initializing after a 409', async () => {
    api.post.mockRejectedValueOnce({
      response: { data: { detail: { code: 'duplicate_task' } } },
    });
    const setActive = vi.fn();
    const setIsProcessing = vi.fn();
    const setStatus = vi.fn();
    const setTaskId = vi.fn();
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'demo',
      setActive,
      setIsProcessing,
      setStatus,
      setTaskId,
      setTranslationDetails: vi.fn(),
      t: (key) => key,
    }));

    await act(() => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
    }));

    expect(setActive).toHaveBeenLastCalledWith(1);
    expect(setIsProcessing).toHaveBeenLastCalledWith(false);
    expect(setStatus).toHaveBeenLastCalledWith('failed');
    expect(setTaskId).toHaveBeenLastCalledWith(null);
  });

  it('asks how to handle a stale archive and retries initial translation with the old archive', async () => {
    api.post.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            code: 'context_release_stale_choice_required',
            context_readiness: {
              archive: {
                release_id: 'release-1',
                current_source_snapshot_hash: 'hash-1',
              },
            },
          },
        },
      },
    }).mockResolvedValueOnce({ data: { task_id: 'task-initial' } });
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'demo',
      setActive: vi.fn(),
      setIsProcessing: vi.fn(),
      setStatus: vi.fn(),
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
      t: (key) => key,
    }));

    await act(async () => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
    }));
    expect(result.current.staleContext.opened).toBe(true);

    await act(async () => result.current.staleContext.choose('use_old_archive'));

    expect(api.post).toHaveBeenLastCalledWith('/api/translate/start', expect.objectContaining({
      stale_choice: 'use_old_archive',
      stale_acknowledgement: {
        choice: 'use_old_archive',
        context_release_id: 'release-1',
        source_snapshot_hash: 'hash-1',
      },
    }));
  });

  it('cancels the stale archive prompt and returns initial translation to configuration', async () => {
    api.post.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            code: 'context_release_stale_choice_required',
            context_readiness: {
              archive: {
                release_id: 'release-1',
                current_source_snapshot_hash: 'hash-1',
              },
            },
          },
        },
      },
    });
    const setActive = vi.fn();
    const setIsProcessing = vi.fn();
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'demo',
      setActive,
      setIsProcessing,
      setStatus: vi.fn(),
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
      t: (key) => key,
    }));

    await act(async () => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
    }));
    await act(async () => result.current.staleContext.cancel());

    expect(api.post).toHaveBeenCalledOnce();
    expect(setActive).toHaveBeenLastCalledWith(1);
    expect(setIsProcessing).toHaveBeenLastCalledWith(false);
  });

  it('uses the backend recovery task action instead of legacy checkpoint endpoints', async () => {
    api.get.mockResolvedValue({ data: {
      task_id: 'task-interrupted',
      checkpoint: { available: true, resumable: true },
      allowed_actions: ['resume_task', 'start_over_task'],
    } });
    api.post.mockResolvedValueOnce({ data: { task_id: 'task-resumed', status: 'queued' } });
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Renamed Project', source_language: 'en' },
      selectedProjectId: 'project-stable-id',
      setActive: vi.fn(),
      setIsProcessing: vi.fn(),
      setStatus: vi.fn(),
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
      resumeEnabled: true,
    }));

    await act(() => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
      use_resume: true,
    }));
    expect(api.get).toHaveBeenCalledWith('/api/projects/project-stable-id/translation-recovery');

    await act(() => result.current.handleStartOver());
    expect(api.post).toHaveBeenCalledWith('/api/tasks/task-interrupted/start-over', {});
    expect(api.post).not.toHaveBeenCalledWith('/api/translation/checkpoint-status', expect.anything());
    expect(api.post).not.toHaveBeenCalledWith('/api/translation/checkpoint', expect.anything());
  });

  it('resumes the backend task instead of starting a new translation task', async () => {
    api.get.mockResolvedValue({ data: {
      task_id: 'task-interrupted',
      checkpoint: { available: true, resumable: true },
      allowed_actions: ['resume_task'],
    } });
    api.post.mockResolvedValueOnce({ data: { task_id: 'task-resumed', status: 'queued' } });
    const setTaskId = vi.fn();
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'project-1',
      setActive: vi.fn(),
      setIsProcessing: vi.fn(),
      setStatus: vi.fn(),
      setTaskId,
      setTranslationDetails: vi.fn(),
      resumeEnabled: true,
    }));

    await act(() => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
      use_resume: true,
    }));
    await act(() => result.current.handleResume());

    expect(api.post).toHaveBeenCalledWith('/api/tasks/task-interrupted/resume', {});
    expect(api.post).not.toHaveBeenCalledWith('/api/translate/start', expect.anything());
    expect(setTaskId).toHaveBeenLastCalledWith('task-resumed');
  });

  it('forces a fresh run when checkpoint resume is disabled', async () => {
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'demo',
      setActive: vi.fn(),
      setIsProcessing: vi.fn(),
      setStatus: vi.fn(),
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
      resumeEnabled: false,
    }));

    await act(() => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
      use_resume: true,
    }));

    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).toHaveBeenCalledWith(
      '/api/translate/start',
      expect.objectContaining({ use_resume: false }),
    );
  });

  it('starts fresh when backend recovery discovery fails', async () => {
    api.get.mockRejectedValue(new Error('recovery unavailable'));
    const { result } = renderHook(() => useInitialTranslationFlow({
      config: { languages: [] },
      notificationStyle: {},
      selectedProject: { game_id: 'victoria3', label: 'Demo', source_language: 'en' },
      selectedProjectId: 'project-1',
      setActive: vi.fn(),
      setIsProcessing: vi.fn(),
      setStatus: vi.fn(),
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
      resumeEnabled: true,
    }));

    await act(() => result.current.handleStartClick({
      ...values,
      reference_reuse_enabled: false,
      use_resume: true,
    }));

    expect(api.post).toHaveBeenCalledWith(
      '/api/translate/start',
      expect.objectContaining({ use_resume: false }),
    );
  });
});

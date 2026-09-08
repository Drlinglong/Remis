import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationService from '../services/translationService';
import { useIncrementalExecution } from './useIncrementalExecution';
import { useStaleTranslationContextRetry } from './useStaleTranslationContextRetry';

vi.mock('../services/translationService', () => ({
  default: { startIncrementalUpdate: vi.fn() },
}));
vi.mock('../services/notificationService', () => ({
  default: { error: vi.fn(), info: vi.fn() },
}));

const buildOptions = () => ({
  addLog: vi.fn(),
  archiveInfo: null,
  completionSourceRef: { current: null },
  connectWebSocket: vi.fn(),
  customSourcePath: 'J:/mod',
  executionInFlightRef: { current: false },
  executing: false,
  i18n: { language: 'en' },
  loading: false,
  notificationStyle: {},
  preScanInFlightRef: { current: false },
  referenceLocalizationPath: 'I:/Victoria 3/game/localization',
  referenceReuseBypassed: false,
  referenceReuseEnabled: true,
  referenceReuseExcludedEntries: [],
  selectedLangs: ['zh-CN'],
  selectedProject: { project_id: 'demo' },
  setActive: vi.fn(),
  setConflictingTaskId: vi.fn(),
  setCurrentTaskId: vi.fn(),
  setCurrentTaskMode: vi.fn(),
  setExecuting: vi.fn(),
  setFinalSummary: vi.fn(),
  setLogs: vi.fn(),
  setProgress: vi.fn(),
  setProgressInfo: vi.fn(),
  staleContextSubmit: async ({ payload, request, onSuccess, onError }) => {
    try {
      const response = await request(payload);
      await onSuccess(response);
      return response;
    } catch (error) {
      onError(error);
      return false;
    }
  },
  t: (key) => key,
});

describe('useIncrementalExecution', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    translationService.startIncrementalUpdate.mockResolvedValue({ data: { task_id: 'task-2' } });
  });

  it('preserves reference reuse settings in the execution payload', async () => {
    const input = buildOptions();
    const { result } = renderHook(() => useIncrementalExecution(input));

    await act(() => result.current());

    expect(translationService.startIncrementalUpdate).toHaveBeenCalledWith(
      'demo',
      expect.objectContaining({
        reference_reuse: {
          enabled: true,
          excluded_entries: [],
          localization_path: 'I:/Victoria 3/game/localization',
        },
      }),
    );
    expect(input.setCurrentTaskId).toHaveBeenCalledWith('task-2');
  });

  it('keeps reference reuse disabled after the user bypasses the library prompt', async () => {
    const input = { ...buildOptions(), referenceReuseBypassed: true };
    const { result } = renderHook(() => useIncrementalExecution(input));

    await act(() => result.current());

    expect(translationService.startIncrementalUpdate).toHaveBeenCalledWith(
      'demo',
      expect.objectContaining({
        reference_reuse: expect.objectContaining({ enabled: false }),
      }),
    );
  });

  it('asks how to handle a stale archive and retries incremental execution with only glossaries', async () => {
    const staleError = {
      response: {
        status: 409,
        data: {
          detail: {
            code: 'context_release_stale_choice_required',
            context_readiness: {
              archive: {
                release_id: 'release-2',
                current_source_snapshot_hash: 'hash-2',
              },
            },
          },
        },
      },
    };
    translationService.startIncrementalUpdate.mockRejectedValueOnce(staleError)
      .mockResolvedValueOnce({ data: { task_id: 'task-2' } });
    const input = buildOptions();
    const { result } = renderHook(() => {
      const staleContext = useStaleTranslationContextRetry();
      const execution = useIncrementalExecution({
        ...input,
        staleContextSubmit: staleContext.submit,
      });
      return { execution, staleContext };
    });

    await act(async () => result.current.execution());
    expect(result.current.staleContext.opened).toBe(true);

    await act(async () => result.current.staleContext.choose('disable_archive'));

    expect(translationService.startIncrementalUpdate).toHaveBeenLastCalledWith(
      'demo',
      expect.objectContaining({
        translation_context_mode: 'archive',
        stale_choice: 'disable_archive',
        stale_acknowledgement: {
          choice: 'disable_archive',
          context_release_id: 'release-2',
          source_snapshot_hash: 'hash-2',
        },
      }),
    );
    expect(input.setCurrentTaskId).toHaveBeenCalledWith('task-2');
  });
});

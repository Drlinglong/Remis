import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationService from '../services/translationService';
import { useIncrementalExecution } from './useIncrementalExecution';

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
});

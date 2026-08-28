import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationService from '../services/translationService';
import { useIncrementalPreScan } from './useIncrementalPreScan';

vi.mock('../services/translationService', () => ({
  default: { startIncrementalUpdate: vi.fn() },
}));
vi.mock('../services/notificationService', () => ({
  default: { error: vi.fn(), info: vi.fn() },
}));

const buildOptions = () => ({
  archiveInfo: null,
  connectWebSocket: vi.fn(),
  customSourcePath: 'J:/mod',
  executionInFlightRef: { current: false },
  executing: false,
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
  setLoading: vi.fn(),
  setLogs: vi.fn(),
  setProgress: vi.fn(),
  setProgressInfo: vi.fn(),
  setScanResults: vi.fn(),
  t: (key) => key,
});

describe('useIncrementalPreScan', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    translationService.startIncrementalUpdate.mockResolvedValue({ data: { task_id: 'task-1' } });
  });

  it('preserves reference reuse settings in the dry-run payload', async () => {
    const input = buildOptions();
    const { result } = renderHook(() => useIncrementalPreScan(input));

    await act(() => result.current());

    expect(translationService.startIncrementalUpdate).toHaveBeenCalledWith(
      'demo',
      expect.objectContaining({
        dry_run: true,
        reference_reuse: {
          enabled: true,
          excluded_entries: [],
          localization_path: 'I:/Victoria 3/game/localization',
        },
      }),
    );
    expect(input.connectWebSocket).toHaveBeenCalledWith('task-1', true);
  });
});

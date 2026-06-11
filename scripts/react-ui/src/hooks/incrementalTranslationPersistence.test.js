import { describe, expect, it, vi } from 'vitest';

import {
  buildIncrementalStateSnapshot,
  readIncrementalStateSnapshot,
  writeIncrementalStateSnapshot,
} from './incrementalTranslationPersistence';
import { INCREMENTAL_STATE_STORAGE_KEY } from './incrementalTranslationPayload';

const createStorage = () => {
  const values = new Map();
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
};

describe('incrementalTranslationPersistence', () => {
  it('builds a serializable snapshot for incremental translation state', () => {
    expect(buildIncrementalStateSnapshot({
      active: 3,
      archiveInfo: { exists: true },
      batchSizeLimit: '12',
      checkpointFound: true,
      checkpointInfo: { completed_count: 2 },
      completionSource: 'websocket',
      concurrencyLimit: '4',
      currentTaskId: 'task-1',
      currentTaskMode: 'execution',
      customSourcePath: 'J:/mod',
      embeddedWorkshopBatchSize: '5',
      embeddedWorkshopConcurrency: '1',
      embeddedWorkshopEnabled: true,
      embeddedWorkshopFollowPrimary: false,
      embeddedWorkshopModel: 'model-b',
      embeddedWorkshopProvider: 'ollama',
      embeddedWorkshopRpm: '20',
      errorKey: null,
      executing: true,
      finalSummary: null,
      loading: false,
      logs: ['started'],
      progress: 55,
      progressInfo: { percent: 55 },
      rpmLimit: '40',
      scanResults: { changed: 1 },
      selectedLangs: ['zh-CN'],
      selectedModel: 'model-a',
      selectedProject: { project_id: 7 },
      selectedProvider: 'gemini',
      showResumeDetails: true,
      showWorkshopSettings: true,
      useResume: true,
    })).toEqual({
      active: 3,
      archiveInfo: { exists: true },
      batchSizeLimit: '12',
      checkpointFound: true,
      checkpointInfo: { completed_count: 2 },
      completionSource: 'websocket',
      concurrencyLimit: '4',
      currentTaskId: 'task-1',
      currentTaskMode: 'execution',
      customSourcePath: 'J:/mod',
      embeddedWorkshopBatchSize: '5',
      embeddedWorkshopConcurrency: '1',
      embeddedWorkshopEnabled: true,
      embeddedWorkshopFollowPrimary: false,
      embeddedWorkshopModel: 'model-b',
      embeddedWorkshopProvider: 'ollama',
      embeddedWorkshopRpm: '20',
      errorKey: null,
      executing: true,
      finalSummary: null,
      loading: false,
      logs: ['started'],
      progress: 55,
      progressInfo: { percent: 55 },
      rpmLimit: '40',
      scanResults: { changed: 1 },
      selectedLangs: ['zh-CN'],
      selectedModel: 'model-a',
      selectedProject: { project_id: 7 },
      selectedProvider: 'gemini',
      showResumeDetails: true,
      showWorkshopSettings: true,
      useResume: true,
    });
  });

  it('reads and writes snapshots through the storage key', () => {
    const storage = createStorage();
    const snapshot = { active: 2, selectedProject: { project_id: 3 } };

    writeIncrementalStateSnapshot(snapshot, storage);

    expect(storage.setItem).toHaveBeenCalledWith(
      INCREMENTAL_STATE_STORAGE_KEY,
      JSON.stringify(snapshot)
    );
    expect(readIncrementalStateSnapshot(storage)).toEqual(snapshot);
  });

  it('returns null when no persisted snapshot exists', () => {
    expect(readIncrementalStateSnapshot(createStorage())).toBeNull();
  });
});

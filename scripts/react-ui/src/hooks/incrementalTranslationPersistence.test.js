import { describe, expect, it, vi } from 'vitest';

import {
  applyIncrementalStateSnapshot,
  buildIncrementalStateSnapshot,
  readIncrementalStateSnapshot,
  resolvePersistedProject,
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

  it('resolves persisted projects against the current project list', () => {
    const currentProject = { project_id: 7, name: 'current' };
    const staleProject = { project_id: 7, name: 'stale' };

    expect(resolvePersistedProject(staleProject, [currentProject])).toBe(currentProject);
    expect(resolvePersistedProject(staleProject, [])).toBe(staleProject);
    expect(resolvePersistedProject(null, [currentProject])).toBeNull();
  });

  it('applies a persisted state snapshot through provided setters and refs', () => {
    const setters = {
      setActive: vi.fn(),
      setArchiveInfo: vi.fn(),
      setCheckpointFound: vi.fn(),
      setCheckpointInfo: vi.fn(),
      setCurrentTaskId: vi.fn(),
      setCurrentTaskMode: vi.fn(),
      setCustomSourcePath: vi.fn(),
      setEmbeddedWorkshopBatchSize: vi.fn(),
      setEmbeddedWorkshopConcurrency: vi.fn(),
      setEmbeddedWorkshopEnabled: vi.fn(),
      setEmbeddedWorkshopFollowPrimary: vi.fn(),
      setEmbeddedWorkshopModel: vi.fn(),
      setEmbeddedWorkshopProvider: vi.fn(),
      setEmbeddedWorkshopRpm: vi.fn(),
      setErrorKey: vi.fn(),
      setExecuting: vi.fn(),
      setFinalSummary: vi.fn(),
      setLoading: vi.fn(),
      setLogs: vi.fn(),
      setProgress: vi.fn(),
      setProgressInfo: vi.fn(),
      setScanResults: vi.fn(),
      setSelectedLangs: vi.fn(),
      setSelectedProject: vi.fn(),
      setShowResumeDetails: vi.fn(),
      setShowWorkshopSettings: vi.fn(),
      setUseResume: vi.fn(),
    };
    const completionSourceRef = { current: null };
    const currentProject = { project_id: 7, name: 'current' };

    applyIncrementalStateSnapshot({
      active: 2,
      archiveInfo: { exists: true },
      checkpointFound: true,
      checkpointInfo: { completed_count: 1 },
      completionSource: 'polling',
      currentTaskId: 'task-1',
      currentTaskMode: 'pre_scan',
      customSourcePath: 'J:/mod',
      embeddedWorkshopBatchSize: 5,
      embeddedWorkshopConcurrency: 2,
      embeddedWorkshopEnabled: true,
      embeddedWorkshopFollowPrimary: false,
      embeddedWorkshopModel: 'model-b',
      embeddedWorkshopProvider: 'ollama',
      embeddedWorkshopRpm: 20,
      errorKey: 'archive_missing',
      executing: false,
      finalSummary: { ok: true },
      loading: false,
      logs: ['done'],
      progress: 100,
      progressInfo: { percent: 100 },
      scanResults: { changed: 1 },
      selectedLangs: ['zh-CN'],
      selectedProject: { project_id: 7, name: 'stale' },
      showResumeDetails: true,
      showWorkshopSettings: true,
      useResume: true,
    }, setters, {
      completionSourceRef,
      projects: [currentProject],
    });

    expect(setters.setSelectedProject).toHaveBeenCalledWith(currentProject);
    expect(setters.setActive).toHaveBeenCalledWith(2);
    expect(setters.setCustomSourcePath).toHaveBeenCalledWith('J:/mod');
    expect(setters.setEmbeddedWorkshopBatchSize).toHaveBeenCalledWith('5');
    expect(setters.setEmbeddedWorkshopConcurrency).toHaveBeenCalledWith('2');
    expect(setters.setEmbeddedWorkshopRpm).toHaveBeenCalledWith('20');
    expect(setters.setCurrentTaskId).toHaveBeenCalledWith('task-1');
    expect(setters.setCurrentTaskMode).toHaveBeenCalledWith('pre_scan');
    expect(completionSourceRef.current).toBe('polling');
  });
});

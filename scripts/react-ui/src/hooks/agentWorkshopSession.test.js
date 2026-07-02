import { describe, expect, it, vi } from 'vitest';

import {
  AGENT_WORKSHOP_STORAGE_KEY,
  appendAgentWorkshopLogSnapshot,
  clearAgentWorkshopSnapshot,
  createAgentWorkshopSnapshot,
  readAgentWorkshopSnapshot,
  writeAgentWorkshopSnapshot,
} from './agentWorkshopSession';

const createStorage = (initial = {}) => {
  const values = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
};

describe('agentWorkshopSession', () => {
  it('round-trips a workflow snapshot through storage', () => {
    const storage = createStorage();
    const snapshot = createAgentWorkshopSnapshot({
      active: 2,
      selectedProjectId: 'project-1',
      archiveInfo: { source_entry_count: 3 },
      projectHistory: [],
      issues: [{ key: 'a' }],
      fixedIssues: [],
      isCached: true,
      searchQuery: 'vic3',
      gameFilter: 'all',
      selectedProvider: 'gemini',
      selectedModel: 'gemini-pro',
      batchSizeLimit: '10',
      concurrencyLimit: '1',
      rpmLimit: '40',
      executing: false,
      progress: 30,
      executionLogs: ['log'],
      executionStats: null,
    });

    writeAgentWorkshopSnapshot(snapshot, storage);

    expect(storage.setItem).toHaveBeenCalledWith(AGENT_WORKSHOP_STORAGE_KEY, JSON.stringify(snapshot));
    expect(readAgentWorkshopSnapshot(storage)).toEqual(snapshot);
  });

  it('falls back to an empty snapshot when persisted JSON is corrupt', () => {
    const storage = createStorage({ [AGENT_WORKSHOP_STORAGE_KEY]: '{bad json' });
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(readAgentWorkshopSnapshot(storage)).toEqual({});

    errorSpy.mockRestore();
  });

  it('appends execution logs without dropping previous snapshot fields', () => {
    const storage = createStorage({
      [AGENT_WORKSHOP_STORAGE_KEY]: JSON.stringify({
        active: 3,
        executionLogs: ['old'],
        selectedProjectId: 'project-1',
      }),
    });

    expect(appendAgentWorkshopLogSnapshot('new', storage)).toHaveLength(2);
    expect(readAgentWorkshopSnapshot(storage)).toMatchObject({
      active: 3,
      selectedProjectId: 'project-1',
    });
    expect(readAgentWorkshopSnapshot(storage).executionLogs[1]).toContain('new');
  });

  it('clears the persisted workflow snapshot', () => {
    const storage = createStorage();

    clearAgentWorkshopSnapshot(storage);

    expect(storage.removeItem).toHaveBeenCalledWith(AGENT_WORKSHOP_STORAGE_KEY);
  });
});

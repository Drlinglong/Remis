import { describe, expect, it, vi } from 'vitest';

import {
  isIncrementalTaskTerminal,
  resyncIncrementalTask,
  shouldResyncIncrementalTask,
} from './incrementalTranslationTaskResync';

describe('incrementalTranslationTaskResync', () => {
  it('treats interruption and cancellation as terminal statuses', () => {
    expect(isIncrementalTaskTerminal('interrupted')).toBe(true);
    expect(isIncrementalTaskTerminal('cancelled')).toBe(true);
    expect(isIncrementalTaskTerminal('running')).toBe(false);
  });

  it('requires restored active work with a task id and mode', () => {
    expect(shouldResyncIncrementalTask({
      currentTaskId: 'task-1',
      currentTaskMode: 'execution',
      executing: true,
      loading: false,
      restorationApplied: true,
      statusResynced: false,
    })).toBe(true);

    expect(shouldResyncIncrementalTask({
      currentTaskId: 'task-1',
      currentTaskMode: 'execution',
      executing: false,
      loading: false,
      restorationApplied: true,
      statusResynced: false,
    })).toBe(false);

    expect(shouldResyncIncrementalTask({
      currentTaskId: 'task-1',
      currentTaskMode: 'execution',
      executing: true,
      loading: false,
      restorationApplied: true,
      statusResynced: true,
    })).toBe(false);
  });

  it('routes terminal restored tasks through the normal task update handler', async () => {
    const projectService = {
      getTaskStatus: vi.fn().mockResolvedValue({
        data: { status: 'completed', summary: { changed: 1 } },
      }),
    };
    const connectWebSocket = vi.fn();
    const handleTaskUpdate = vi.fn();

    await expect(resyncIncrementalTask({
      connectWebSocket,
      currentTaskId: 'task-1',
      currentTaskMode: 'pre_scan',
      handleTaskUpdate,
      projectService,
    })).resolves.toEqual({ source: 'polling', terminal: true });

    expect(handleTaskUpdate).toHaveBeenCalledWith(
      { status: 'completed', summary: { changed: 1 } },
      true,
      'polling'
    );
    expect(connectWebSocket).not.toHaveBeenCalled();
  });

  it('reconnects websocket for non-terminal restored tasks', async () => {
    const projectService = {
      getTaskStatus: vi.fn().mockResolvedValue({ data: { status: 'running' } }),
    };
    const connectWebSocket = vi.fn();

    await expect(resyncIncrementalTask({
      connectWebSocket,
      currentTaskId: 'task-2',
      currentTaskMode: 'execution',
      handleTaskUpdate: vi.fn(),
      projectService,
    })).resolves.toEqual({ source: 'websocket', terminal: false });

    expect(connectWebSocket).toHaveBeenCalledWith('task-2', false);
  });

  it('routes interrupted tasks through the terminal update handler', async () => {
    const projectService = {
      getTaskStatus: vi.fn().mockResolvedValue({ data: { status: 'interrupted' } }),
    };
    const handleTaskUpdate = vi.fn();
    const connectWebSocket = vi.fn();

    await expect(resyncIncrementalTask({
      connectWebSocket,
      currentTaskId: 'task-interrupted',
      currentTaskMode: 'execution',
      handleTaskUpdate,
      projectService,
    })).resolves.toEqual({ source: 'polling', terminal: true });

    expect(handleTaskUpdate).toHaveBeenCalledWith(
      { status: 'interrupted' },
      false,
      'polling',
    );
    expect(connectWebSocket).not.toHaveBeenCalled();
  });

  it('falls back to websocket reconnect when status polling fails', async () => {
    const projectService = {
      getTaskStatus: vi.fn().mockRejectedValue(new Error('offline')),
    };
    const connectWebSocket = vi.fn();

    await expect(resyncIncrementalTask({
      connectWebSocket,
      currentTaskId: 'task-3',
      currentTaskMode: 'pre_scan',
      handleTaskUpdate: vi.fn(),
      projectService,
    })).resolves.toEqual({
      source: 'websocket',
      terminal: false,
      recoveredFromError: true,
    });

    expect(connectWebSocket).toHaveBeenCalledWith('task-3', true);
  });
});

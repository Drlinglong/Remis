import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  TRANSLATION_RECOVERY_ACTIONS,
  buildTranslationCheckpointEndpoint,
  buildTranslationRecoveryActionEndpoint,
  buildTranslationRecoveryEndpoint,
  isRecoveryActionAllowed,
  normalizeTranslationRecovery,
  TranslationRecoveryActionError,
  useTranslationRecovery,
} from './useTranslationRecovery';

const recovery = {
  task_id: 'task-interrupted',
  project_id: 'project-1',
  status: 'interrupted',
  progress: 42,
  checkpoint: {
    available: true,
    resumable: true,
    checkpoint_id: 'checkpoint-1',
    revision: 7,
  },
  allowed_actions: ['resume_task', 'start_over_task', 'clear_checkpoint'],
};

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

describe('translation recovery contract', () => {
  it('normalizes a backend recovery projection without deriving resumability from files', () => {
    const normalized = normalizeTranslationRecovery({ data: { recovery } });

    expect(normalized).toMatchObject(recovery);
    expect(normalized.allowed_actions).toEqual([
      'resume_task',
      'start_over_task',
      'clear_checkpoint',
    ]);
    expect(normalized.checkpoint.resumable).toBe(true);
    expect(isRecoveryActionAllowed(normalized, TRANSLATION_RECOVERY_ACTIONS.RESUME)).toBe(true);
    expect(isRecoveryActionAllowed({ ...normalized, allowed_actions: [] }, TRANSLATION_RECOVERY_ACTIONS.RESUME)).toBe(false);
  });

  it('builds encoded project and task endpoints', () => {
    expect(buildTranslationRecoveryEndpoint('project/1')).toBe('/api/projects/project%2F1/translation-recovery');
    expect(buildTranslationCheckpointEndpoint('project/1')).toBe('/api/projects/project%2F1/translation-checkpoint');
    expect(buildTranslationRecoveryActionEndpoint('task/1', TRANSLATION_RECOVERY_ACTIONS.RESUME))
      .toBe('/api/tasks/task%2F1/resume');
    expect(buildTranslationRecoveryActionEndpoint('task/1', TRANSLATION_RECOVERY_ACTIONS.START_OVER))
      .toBe('/api/tasks/task%2F1/start-over');
  });

  it('loads backend recovery and uses only allowed actions for mutations', async () => {
    const apiClient = {
      get: vi.fn().mockResolvedValue({ data: recovery }),
      post: vi.fn().mockResolvedValue({
        data: {
          task_id: 'task-resumed',
          status: 'queued',
          checkpoint: { available: false, resumable: false },
          allowed_actions: ['view_task'],
        },
      }),
    };
    const { result } = renderHook(() => useTranslationRecovery('project-1', { apiClient }));

    await waitFor(() => expect(result.current.recovery?.task_id).toBe('task-interrupted'));
    expect(apiClient.get).toHaveBeenCalledWith('/api/projects/project-1/translation-recovery');
    expect(result.current.canResume).toBe(true);

    await act(async () => {
      await result.current.resume({ idempotency_key: 'resume-1' });
    });
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/tasks/task-interrupted/resume',
      { idempotency_key: 'resume-1', expected_checkpoint_revision: 7 },
    );
    expect(result.current.recovery.task_id).toBe('task-resumed');
    expect(result.current.canResume).toBe(false);
  });

  it('rejects actions absent from backend allowed_actions without making a request', async () => {
    const apiClient = {
      get: vi.fn().mockResolvedValue({
        data: { ...recovery, allowed_actions: ['view_task'] },
      }),
      post: vi.fn(),
    };
    const { result } = renderHook(() => useTranslationRecovery('project-1', { apiClient }));

    await waitFor(() => expect(result.current.recovery).not.toBeNull());
    let rejectedError;
    await act(async () => {
      try {
        await result.current.resume();
      } catch (error) {
        rejectedError = error;
      }
    });
    expect(rejectedError).toBeInstanceOf(TranslationRecoveryActionError);
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('posts start-over to the backend task action endpoint', async () => {
    const apiClient = {
      get: vi.fn().mockResolvedValue({ data: recovery }),
      post: vi.fn().mockResolvedValue({
        data: { task_id: 'task-fresh', status: 'queued', allowed_actions: ['view_task'] },
      }),
    };
    const { result } = renderHook(() => useTranslationRecovery('project-1', { apiClient }));

    await waitFor(() => expect(result.current.canStartOver).toBe(true));
    await act(async () => {
      await result.current.startOver({ idempotency_key: 'start-over-1' });
    });
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/tasks/task-interrupted/start-over',
      { idempotency_key: 'start-over-1' },
    );
  });

  it('clears the project checkpoint slot through the project endpoint', async () => {
    const apiClient = {
      get: vi.fn().mockResolvedValue({ data: recovery }),
      post: vi.fn(),
      delete: vi.fn().mockResolvedValue({
        data: {
          ...recovery,
          checkpoint: { available: false, resumable: false },
          allowed_actions: ['return_to_workflow'],
        },
      }),
    };
    const { result } = renderHook(() => useTranslationRecovery('project-1', { apiClient }));

    await waitFor(() => expect(result.current.canClearCheckpoint).toBe(true));
    await act(async () => {
      await result.current.clearCheckpoint();
    });

    expect(apiClient.delete).toHaveBeenCalledWith(
      '/api/projects/project-1/translation-checkpoint',
    );
    expect(result.current.recovery.checkpoint.available).toBe(false);
    expect(result.current.canClearCheckpoint).toBe(false);
  });

  it('does not load or infer recovery when no project is selected', async () => {
    const apiClient = { get: vi.fn(), post: vi.fn() };
    const { result } = renderHook(() => useTranslationRecovery(null, { apiClient }));

    await waitFor(() => expect(result.current.phase).toBe('idle'));
    expect(apiClient.get).not.toHaveBeenCalled();
    expect(result.current.recovery).toBeNull();
    expect(result.current.canResume).toBe(false);
  });

  it('hides the prior project recovery immediately and ignores its late response after a project switch', async () => {
    const projectA = deferred();
    const projectB = deferred();
    const apiClient = {
      get: vi.fn((url) => (url.includes('project-a') ? projectA.promise : projectB.promise)),
      post: vi.fn(),
      delete: vi.fn(),
    };
    const { result, rerender } = renderHook(
      ({ projectId }) => useTranslationRecovery(projectId, { apiClient }),
      { initialProps: { projectId: 'project-a' } },
    );

    rerender({ projectId: 'project-b' });
    expect(result.current.recovery).toBeNull();
    expect(result.current.canResume).toBe(false);
    await expect(result.current.resume()).rejects.toBeInstanceOf(TranslationRecoveryActionError);
    expect(apiClient.post).not.toHaveBeenCalled();

    projectB.resolve({ data: { ...recovery, project_id: 'project-b', task_id: 'task-b' } });
    await waitFor(() => expect(result.current.recovery?.task_id).toBe('task-b'));
    projectA.resolve({ data: { ...recovery, project_id: 'project-a', task_id: 'task-a' } });
    await act(async () => projectA.promise);
    expect(result.current.recovery?.task_id).toBe('task-b');
  });

  it('rejects recovery actions when the backend project id conflicts with the owning project', async () => {
    const apiClient = {
      get: vi.fn().mockResolvedValue({ data: { ...recovery, project_id: 'other-project' } }),
      post: vi.fn(),
      delete: vi.fn(),
    };
    const { result } = renderHook(() => useTranslationRecovery('project-1', { apiClient }));

    await waitFor(() => expect(result.current.recovery?.task_id).toBe('task-interrupted'));
    expect(result.current.canResume).toBe(false);
    await expect(result.current.resume()).rejects.toBeInstanceOf(TranslationRecoveryActionError);
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('stays idle when automatic recovery loading is disabled', () => {
    const apiClient = { get: vi.fn(), post: vi.fn(), delete: vi.fn() };
    const { result } = renderHook(() => useTranslationRecovery('project-1', {
      apiClient,
      autoLoad: false,
    }));

    expect(result.current.phase).toBe('idle');
    expect(result.current.isLoading).toBe(false);
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it('invalidates all actions after a project switch and keeps the new project response', async () => {
    const projectBRecovery = deferred();
    const apiClient = {
      get: vi.fn((url) => (url.includes('project-1')
        ? Promise.resolve({ data: recovery })
        : projectBRecovery.promise)),
      post: vi.fn(),
      delete: vi.fn(),
    };
    const { result, rerender } = renderHook(
      ({ projectId }) => useTranslationRecovery(projectId, { apiClient }),
      { initialProps: { projectId: 'project-1' } },
    );

    await waitFor(() => expect(result.current.canClearCheckpoint).toBe(true));
    rerender({ projectId: 'project-2' });
    expect(result.current.canResume).toBe(false);
    expect(result.current.canStartOver).toBe(false);
    expect(result.current.canClearCheckpoint).toBe(false);

    await expect(result.current.resume()).rejects.toBeInstanceOf(TranslationRecoveryActionError);
    await expect(result.current.startOver({})).rejects.toBeInstanceOf(TranslationRecoveryActionError);
    await expect(result.current.clearCheckpoint()).rejects.toBeInstanceOf(TranslationRecoveryActionError);
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(apiClient.delete).not.toHaveBeenCalled();

    projectBRecovery.resolve({
      data: {
        ...recovery,
        task_id: 'task-project-2',
        project_id: 'project-2',
        allowed_actions: ['view_task'],
      },
    });
    await waitFor(() => expect(result.current.recovery?.project_id).toBe('project-2'));
  });

  it('keeps an in-flight checkpoint clear bound to the project that authorized it', async () => {
    const clearResponse = deferred();
    const projectBRecovery = deferred();
    const apiClient = {
      get: vi.fn((url) => (url.includes('project-1')
        ? Promise.resolve({ data: recovery })
        : projectBRecovery.promise)),
      post: vi.fn(),
      delete: vi.fn(() => clearResponse.promise),
    };
    const { result, rerender } = renderHook(
      ({ projectId }) => useTranslationRecovery(projectId, { apiClient }),
      { initialProps: { projectId: 'project-1' } },
    );

    await waitFor(() => expect(result.current.canClearCheckpoint).toBe(true));
    let clearPromise;
    act(() => {
      clearPromise = result.current.clearCheckpoint();
    });
    expect(apiClient.delete).toHaveBeenCalledWith('/api/projects/project-1/translation-checkpoint');

    rerender({ projectId: 'project-2' });
    clearResponse.resolve({
      data: {
        ...recovery,
        checkpoint: { available: false, resumable: false },
        allowed_actions: [],
      },
    });
    await act(async () => clearPromise);
    expect(result.current.recovery).toBeNull();

    projectBRecovery.resolve({
      data: {
        ...recovery,
        task_id: 'task-project-2',
        project_id: 'project-2',
        allowed_actions: ['view_task'],
      },
    });
    await waitFor(() => expect(result.current.recovery?.project_id).toBe('project-2'));
  });
});
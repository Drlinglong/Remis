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
  },
  allowed_actions: ['resume_task', 'start_over_task', 'clear_checkpoint'],
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
      { idempotency_key: 'resume-1' },
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
});

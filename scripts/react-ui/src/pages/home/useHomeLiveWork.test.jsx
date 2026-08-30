import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useHomeLiveWork } from './useHomeLiveWork';
import api from '../../utils/api';

const navigateMock = vi.fn();
const refreshTasksMock = vi.fn();
let taskCenterState;

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('../../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => taskCenterState,
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('useHomeLiveWork', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    taskCenterState = {
      attentionCount: 1,
      loading: false,
      refreshTasks: refreshTasksMock,
      tasks: [
        { task_id: 'task-1', status: 'running' },
        { task_id: 'task-2', status: 'failed', allowed_actions: ['archive_task'] },
        { task_id: 'task-3', status: 'queued' },
        { task_id: 'task-4', status: 'completed' },
      ],
    };
    refreshTasksMock.mockResolvedValue(undefined);
  });

  it('derives live work from Task Center without issuing a task GET', () => {
    const { result } = renderHook(() => useHomeLiveWork());

    expect(result.current.visibleTasks.map((task) => task.task_id)).toEqual([
      'task-1',
      'task-2',
      'task-4',
    ]);
    expect(result.current.primaryTask.task_id).toBe('task-1');
    expect(api.get).not.toHaveBeenCalled();

    act(() => result.current.openTask(result.current.primaryTask));
    expect(navigateMock).toHaveBeenCalledWith('/tasks/task-1');
  });

  it('archives one task, refreshes Task Center quietly, and scopes errors to that task', async () => {
    api.post.mockRejectedValueOnce(new Error('archive unavailable'));
    const { result } = renderHook(() => useHomeLiveWork());

    await act(async () => result.current.markHandled(taskCenterState.tasks[1]));
    await waitFor(() => expect(result.current.handleErrorTaskId).toBe('task-2'));
    expect(api.post).toHaveBeenCalledWith('/api/tasks/task-2/archive');
    expect(refreshTasksMock).not.toHaveBeenCalled();
    expect(result.current.handleError).toBe('archive unavailable');

    api.post.mockResolvedValueOnce({ data: {} });
    await act(async () => result.current.markHandled(taskCenterState.tasks[1]));
    expect(refreshTasksMock).toHaveBeenCalledWith({ quiet: true });
    expect(result.current.handleError).toBe('');
  });
});

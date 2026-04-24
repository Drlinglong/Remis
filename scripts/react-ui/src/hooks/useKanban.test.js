import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useKanban } from './useKanban';
import api from '../utils/api';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

vi.mock('uuid', () => ({
  v4: () => 'note-123',
}));

describe('useKanban', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads kanban board data for a project', async () => {
    api.get.mockResolvedValue({
      data: {
        tasks: {
          a: { id: 'a', title: 'Task A', status: 'todo' },
        },
        column_order: ['todo', 'done'],
      },
    });

    const { result } = renderHook(() => useKanban('proj-1'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.get).toHaveBeenCalledWith('/api/project/proj-1/kanban');
    expect(result.current.tasks).toEqual([{ id: 'a', title: 'Task A', status: 'todo' }]);
    expect(result.current.columns).toEqual(['todo', 'done']);
  });

  it('adds a note task and persists the updated board', async () => {
    api.get.mockResolvedValue({ data: { tasks: {}, column_order: ['todo', 'done'] } });

    const { result } = renderHook(() => useKanban('proj-2'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.addNoteTask('done');
    });

    expect(result.current.tasks[0]).toMatchObject({
      id: 'note-123',
      type: 'note',
      status: 'done',
      title: 'project_management.kanban.new_task',
    });
  });

  it('refreshes the board after triggering backend refresh', async () => {
    api.get
      .mockResolvedValueOnce({ data: { tasks: {}, column_order: ['todo'] } })
      .mockResolvedValueOnce({
        data: {
          tasks: {
            b: { id: 'b', title: 'Task B', status: 'proofreading' },
          },
          column_order: ['todo', 'proofreading'],
        },
      });
    api.post.mockResolvedValue({ data: { ok: true } });

    const { result } = renderHook(() => useKanban('proj-3'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.refreshBoard();
    });

    expect(api.post).toHaveBeenCalledWith('/api/project/proj-3/refresh');
    expect(api.get).toHaveBeenLastCalledWith('/api/project/proj-3/kanban');
    expect(result.current.tasks).toEqual([{ id: 'b', title: 'Task B', status: 'proofreading' }]);
    expect(result.current.columns).toEqual(['todo', 'proofreading']);
  });
});

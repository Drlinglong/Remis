import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import api from '../utils/api';
import { TaskCenterProvider } from './TaskCenterContext';
import { useTaskCenter } from './TaskCenterContextCore';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

function ContextProbe() {
  const {
    activeCount,
    attentionCount,
    loading,
    tasks,
  } = useTaskCenter();
  return (
    <div>
      <span>{loading ? 'loading' : 'ready'}</span>
      <span>active:{activeCount}</span>
      <span>attention:{attentionCount}</span>
      {tasks.map((task) => <span key={task.task_id}>{task.title}</span>)}
    </div>
  );
}

describe('TaskCenterProvider', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('loads the complete actionable queue separately from the latest completion', async () => {
    api.get.mockImplementation((_url, { params }) => {
      if (params.active_only) {
        return Promise.resolve({
          data: {
            tasks: [{ task_id: 'old-running', title: 'Older running task', status: 'running' }],
            active_count: 1,
            attention_count: 0,
          },
        });
      }
      return Promise.resolve({
        data: {
          tasks: [{ task_id: 'latest-completed', title: 'Latest completed task', status: 'completed' }],
        },
      });
    });

    render(
      <TaskCenterProvider>
        <ContextProbe />
      </TaskCenterProvider>,
    );

    await waitFor(() => expect(screen.getByText('ready')).toBeInTheDocument());

    expect(api.get).toHaveBeenCalledWith('/api/tasks', {
      params: { active_only: true, limit: 200 },
    });
    expect(api.get).toHaveBeenCalledWith('/api/tasks', {
      params: { status: 'completed', limit: 1 },
    });
    expect(screen.getByText('Older running task')).toBeInTheDocument();
    expect(screen.getByText('Latest completed task')).toBeInTheDocument();
    expect(screen.getByText('active:1')).toBeInTheDocument();
  });
});

import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import api from '../utils/api';
import { TaskCenterProvider } from './TaskCenterContext';

vi.mock('../utils/api', () => ({
  default: { get: vi.fn() },
}));

describe('Task Center immediate refresh', () => {
  it('refreshes immediately when a completed foreground workflow records a task', async () => {
    api.get.mockResolvedValue({
      data: {
        tasks: [],
        active_count: 0,
        attention_count: 0,
      },
    });

    render(
      <TaskCenterProvider>
        <div>child</div>
      </TaskCenterProvider>,
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    window.dispatchEvent(new CustomEvent('remis:task-created', {
      detail: { taskId: 'format-scan-zero-issues' },
    }));

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(4));
    expect(api.get).toHaveBeenLastCalledWith('/api/tasks', {
      params: { status: 'completed', limit: 1 },
    });
  });
});

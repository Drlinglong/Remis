import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TaskCenterDrawer } from './TaskCenterDrawer';
import api from '../../utils/api';

const navigateMock = vi.fn();
const closeTaskCenterMock = vi.fn();
const refreshTasksMock = vi.fn();
const translateMock = (key) => key;
let taskCenterState;

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: translateMock }),
}));

vi.mock('../../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => taskCenterState,
}));

vi.mock('../../utils/api', () => ({
  default: { post: vi.fn() },
}));

vi.mock('./TaskSummaryCard', () => ({
  TaskSummaryCard: ({ task, onHandle, onOpen }) => (
    <div>
      <button type="button" onClick={() => onOpen(task)}>{task.title}</button>
      {task.allowed_actions?.includes('archive_task') && (
        <button type="button" onClick={() => onHandle(task)}>mark handled</button>
      )}
    </div>
  ),
}));

vi.mock('@mantine/core', async () => {
  const actual = await vi.importActual('@mantine/core');
  return {
    ...actual,
    Drawer: ({ opened, children }) => (opened ? <div>{children}</div> : null),
    ScrollArea: ({ children }) => <div>{children}</div>,
  };
});

const { MantineProvider } = await import('@mantine/core');

describe('TaskCenterDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    taskCenterState = {
      attentionCount: 1,
      closeTaskCenter: closeTaskCenterMock,
      loading: false,
      opened: true,
      refreshTasks: refreshTasksMock,
      tasks: [{
        task_id: 'failed-task-older',
        title: 'Older failed task',
        status: 'failed',
        allowed_actions: ['view_task', 'archive_task'],
      }],
    };
  });

  it('opens the exact selected task instead of a shared workflow route', () => {
    render(<MantineProvider><TaskCenterDrawer /></MantineProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Older failed task' }));

    expect(closeTaskCenterMock).toHaveBeenCalledOnce();
    expect(navigateMock).toHaveBeenCalledWith('/tasks/failed-task-older');
  });

  it('keeps only the latest completed task visible and opens its exact record', () => {
    taskCenterState.tasks = [
      {
        task_id: 'completed-scan-latest',
        title: 'Latest completed scan',
        status: 'completed',
      },
      {
        task_id: 'running-task',
        title: 'Running task',
        status: 'running',
      },
      {
        task_id: 'completed-scan-older',
        title: 'Older completed scan',
        status: 'completed',
      },
    ];

    render(<MantineProvider><TaskCenterDrawer /></MantineProvider>);

    expect(screen.getByRole('button', { name: 'Running task' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Older completed scan' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Latest completed scan' }));

    expect(closeTaskCenterMock).toHaveBeenCalledOnce();
    expect(navigateMock).toHaveBeenCalledWith('/tasks/completed-scan-latest');
  });

  it('marks a resolved terminal task as handled and refreshes the queue', async () => {
    api.post.mockResolvedValue({ data: { archived_at: '2026-07-22T01:00:00Z' } });
    refreshTasksMock.mockResolvedValue(undefined);
    render(<MantineProvider><TaskCenterDrawer /></MantineProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'mark handled' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/tasks/failed-task-older/archive');
      expect(refreshTasksMock).toHaveBeenCalledWith({ quiet: true });
    });
  });
});

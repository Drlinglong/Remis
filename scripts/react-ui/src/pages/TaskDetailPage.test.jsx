import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TaskDetailPage from './TaskDetailPage';
import api from '../utils/api';

const navigateMock = vi.fn();
const openTaskCenterMock = vi.fn();
const refreshTasksMock = vi.fn();
let taskIdParam = 'failed-task';
const translateMock = (key, options) => {
  if (key === 'task_center.kind.initial_translation') return 'Initial translation';
  if (key === 'game_name_victoria3') return 'Victoria 3';
  return options?.defaultValue || key;
};

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
  useParams: () => ({ taskId: taskIdParam }),
}));

vi.mock('../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => ({
    openTaskCenter: openTaskCenterMock,
    refreshTasks: refreshTasksMock,
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translateMock,
    i18n: { language: 'en' },
  }),
}));

const { MantineProvider } = await import('@mantine/core');

const failedTask = {
  task_id: 'failed-task',
  kind: 'initial_translation',
  title: 'Failed translation attempt',
  status: 'failed',
  progress: 35,
  created_by: { type: 'user', label: 'User' },
  created_at: '2026-07-22T00:00:00Z',
  started_at: '2026-07-22T00:00:01Z',
  finished_at: '2026-07-22T00:00:09Z',
  attention_reason: 'Provider request failed',
  source_route: '/translation',
  project_id: 'project-demo',
  project_context: { name: 'Remis Plan - Demo Mod', game_id: 'victoria3' },
  allowed_actions: ['view_task', 'retry', 'archive_task'],
  checkpoint: {},
  result: {},
  events: [{
    event_id: 'event-failed',
    timestamp: '2026-07-22T00:00:09Z',
    level: 'error',
    message: 'The selected request failed',
  }],
  children: [],
};

describe('TaskDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    taskIdParam = 'failed-task';
    api.get.mockResolvedValue({ data: failedTask });
  });

  it('loads and displays the exact task selected by the route', async () => {
    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/tasks/failed-task');
    });
    expect((await screen.findAllByText('Failed translation attempt')).length).toBeGreaterThan(0);
    expect(screen.getByText('The selected request failed')).toBeInTheDocument();
    expect(screen.getByText('Remis Plan - Demo Mod — Victoria 3')).toBeInTheDocument();
    expect(screen.getAllByText('Initial translation').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('task_center.blocking')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'task_detail.back_to_workflow' }));
    expect(navigateMock).toHaveBeenCalledWith('/translation');
  });
});

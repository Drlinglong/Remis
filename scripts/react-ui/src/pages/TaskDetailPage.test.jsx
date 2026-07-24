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
  if (key === 'glossary_health_task_title') return `Localized health check (${options.count})`;
  if (key === 'glossary_health_completed_message') {
    return `Localized health summary ${options.score}/100, ${options.count} issues`;
  }
  if (key === 'glossary_health_issue_placeholder_mismatch') {
    return 'Localized placeholder mismatch';
  }
  return options?.defaultValue || key;
};

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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
    expect(screen.getByText('Remis Plan - Demo Mod')).toBeInTheDocument();
    expect(screen.getByText('Victoria 3').closest('[data-game-color]')).toHaveAttribute('data-game-color', 'blue');
    expect(screen.getAllByText('Initial translation').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('task_center.blocking')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'task_detail.back_to_workflow' }));
    expect(navigateMock).toHaveBeenCalledWith('/translation');

    fireEvent.click(screen.getByRole('button', { name: 'context_sidebar.project_details: Remis Plan - Demo Mod' }));
    expect(navigateMock).toHaveBeenCalledWith('/project-management/project-demo');
  });

  it('restores the detailed glossary health report and advisory result', async () => {
    taskIdParam = 'health-task';
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        task_id: 'health-task',
        kind: 'glossary_health_check',
        title: 'Check glossary assets',
        status: 'completed',
        progress: 100,
        attention_reason: null,
        source_route: '/glossary',
        allowed_actions: ['view_task', 'archive_task'],
        result: {
          types: ['glossary_health_report', 'advisory_review'],
          summary: 'Glossary health score 81/100.',
          metadata: {
            score: 81,
            issue_count: 2,
            target_lang: 'zh-CN',
            mutations_applied: false,
            issues: [{
              code: 'placeholder_mismatch',
              severity: 'error',
              count: 2,
              message: 'Source and translation placeholders differ',
              items: [{
                detail: 'zh-CN placeholders differ.',
                entry_id: 'token-a',
                glossary_id: 7,
                glossary_name: 'Health Test',
                game_id: 'vic3',
                source: 'Army $COUNT$',
              }],
            }],
            ai_review_status: 'completed',
            ai_advice: [{
              issue_code: 'placeholder_mismatch',
              recommendation: 'Review placeholder parity manually.',
              rationale: 'The deterministic evidence shows different token sets.',
            }],
          },
        },
      },
    });
    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByTestId('glossary-health-task-result')).toBeInTheDocument();
    expect(screen.getByText('glossary_health_score 81/100')).toBeInTheDocument();
    expect(screen.getByText('Localized health summary 81/100, 2 issues')).toBeInTheDocument();
    expect(screen.getByText('Localized placeholder mismatch')).toBeInTheDocument();
    expect(screen.queryByText('Glossary health score 81/100.')).not.toBeInTheDocument();
    expect(screen.queryByText('Source and translation placeholders differ')).not.toBeInTheDocument();
    expect(screen.getByText('glossary_health_read_only')).toBeInTheDocument();
    expect(screen.queryByTestId('glossary-health-workbench')).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Review and fix issues' }));
    expect(navigateMock).toHaveBeenCalledWith('/tasks/health-task/glossary-health');

    fireEvent.click(screen.getByRole('button', { name: 'task_detail.back_to_workflow' }));
    expect(navigateMock).toHaveBeenCalledWith('/glossary-manager');
  });
});

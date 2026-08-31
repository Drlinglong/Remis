import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import TaskDetailPage from './TaskDetailPage';
import api from '../utils/api';

const navigateMock = vi.fn();
const openTaskCenterMock = vi.fn();
const refreshTasksMock = vi.fn();
let taskIdParam = 'failed-task';
const translateMock = (key, options) => {
  if (key === 'task_center.kind.initial_translation') return 'Initial translation';
  if (key === 'task_center.kind.incremental_translation') return 'Incremental translation';
  if (key === 'task_center.kind.agent_workshop') return 'Format Repair';
  if (key === 'agent_workshop.description') return 'Check and batch-repair format issues in localization files.';
  if (key === 'game_name_victoria3') return 'Victoria 3';
  if (key === 'glossary_health_task_title') return `Localized health check (${options.count})`;
  if (key === 'glossary_health_completed_message') {
    return `Localized health summary ${options.score}/100, ${options.count} issues`;
  }
  if (key === 'glossary_health_issue_placeholder_mismatch') {
    return 'Localized placeholder mismatch';
  }
  if (key === 'glossary_health_partial_status') return 'Partially completed';
  if (key === 'glossary_health_partial_message') return 'Deterministic report available; AI advice unavailable.';
  if (key === 'glossary_health_ai_unavailable_event') return 'AI advice unavailable event';
  if (key === 'glossary_health_event_queued') return 'Localized inspection queued';
  if (key === 'glossary_health_event_deterministic_started') return 'Localized deterministic checks started';
  if (key === 'glossary_health_event_deterministic_found') return `Localized ${options.count} findings`;
  if (key === 'glossary_health_event_ai_started') return 'Localized AI advice started';
  if (key === 'glossary_health_completed_title') return 'Localized inspection completed';
  if (key === 'task_detail.blocking_description') return 'Localized project write lock';
  if (key === 'glossary_health_no_model_loaded') return 'Load a local model before retrying.';
  if (key === 'task_presentation.provider_failure.forbidden.title') return 'Provider access was forbidden';
  if (key === 'task_presentation.provider_failure.forbidden.action') return 'Check account model access, then retry.';
  return options?.defaultValue || key;
};

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
  useParams: () => ({ taskId: taskIdParam }),
}));

vi.mock('../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => ({
    openTaskCenter: openTaskCenterMock,
    refreshTasks: refreshTasksMock,
  }),
}));

vi.mock('../context/TutorialContextCore', () => ({
  useTutorial: () => ({ setPageContext: vi.fn() }),
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
  allowed_actions: ['view_task', 'return_to_workflow', 'archive_task'],
  checkpoint: {},
  result: {},
  events: [{
    event_id: 'event-failed',
    timestamp: '2026-07-22T00:00:09Z',
    level: 'error',
    audience: 'user',
    message: 'The selected request failed',
  }],
  children: [],
  child_aggregate: { total: 0, active: 0, attention: 0, completed: 0, progress: 0 },
};

describe('TaskDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    taskIdParam = 'failed-task';
    api.get.mockResolvedValue({ data: failedTask });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('loads and displays the exact task selected by the route', async () => {
    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/tasks/failed-task', {
        params: { include_diagnostics: true },
      });
    });
    expect((await screen.findAllByText('Failed translation attempt')).length).toBeGreaterThan(0);
    expect(screen.getByText('The selected request failed')).toBeInTheDocument();
    expect(screen.getByText('Remis Plan - Demo Mod')).toBeInTheDocument();
    expect(screen.getByText('Victoria 3').closest('[data-game-color]')).toHaveAttribute('data-game-color', 'blue');
    expect(screen.getAllByText('Initial translation').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('task_center.blocking')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'task_detail.back_to_workflow' }));
    expect(navigateMock).toHaveBeenCalledWith('/translation', {
      state: {
        projectId: 'project-demo',
        taskId: 'failed-task',
      },
    });

    fireEvent.click(screen.getByRole('button', { name: 'context_sidebar.project_details: Remis Plan - Demo Mod' }));
    expect(navigateMock).toHaveBeenCalledWith('/project-management/project-demo');
  });

  it('shows an explicit forbidden error with a corrective next step', async () => {
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        attention_reason_code: 'provider_forbidden',
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByText('Provider access was forbidden')).toBeInTheDocument();
    expect(screen.getAllByText('Check account model access, then retry.')).toHaveLength(2);
  });

  it('loads diagnostics by default and expands failed task logs', async () => {
    api.get.mockImplementation(() => Promise.resolve({
      data: {
        ...failedTask,
        events: [
          ...failedTask.events,
          {
            event_id: 'event-diagnostic',
            timestamp: '2026-07-22T00:00:09Z',
            level: 'debug',
            audience: 'diagnostic',
            message: 'worker=2 batch=4',
          },
        ],
      },
    }));

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByText('The selected request failed')).toBeInTheDocument();
    expect(screen.getByText('worker=2 batch=4')).toBeVisible();
    expect(screen.getByText('task_detail.diagnostic')).toBeInTheDocument();
    expect(screen.queryByRole('switch', { name: 'task_detail.show_diagnostics' })).not.toBeInTheDocument();
    expect(screen.getByTestId('task-event-log')).toHaveAttribute('open');
    expect(screen.getByRole('link', { name: 'task_detail.export_log' })).toHaveAttribute(
      'href',
      '/api/tasks/failed-task/events/export?include_diagnostics=true',
    );
  });

  it('relabels persisted Agent Workshop tasks as Format Repair', async () => {
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        task_id: 'legacy-format-repair',
        kind: 'agent_workshop',
        title: 'Agent Workshop repair',
      },
    });
    taskIdParam = 'legacy-format-repair';

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect((await screen.findAllByText('Format Repair')).length).toBeGreaterThan(0);
    expect(screen.getByText('Check and batch-repair format issues in localization files.')).toBeInTheDocument();
    expect(screen.queryByText('Agent Workshop repair')).not.toBeInTheDocument();
  });

  it('does not expose persisted English title or recovery copy for a failed incremental task', async () => {
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        kind: 'incremental_translation',
        title: 'Incremental translation failed',
        stage: 'Failed',
        stage_code: 'failed',
        attention_reason: 'Return to Incremental Translation, review the task diagnostics, and retry.',
        attention_reason_code: 'incremental_translation_failed_review_diagnostics',
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect((await screen.findAllByText('Incremental translation')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Incremental translation failed')).not.toBeInTheDocument();
    expect(screen.queryByText(/Return to Incremental Translation/)).not.toBeInTheDocument();
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('task_presentation.next_step.review_failure').length).toBeGreaterThan(0);
  });

  it('localizes the structured project write lock instead of exposing backend English', async () => {
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        status: 'running',
        blocking: true,
        blocking_reason: 'This task is changing project files. Conflicting writes are blocked until it finishes.',
        blocking_reason_code: 'project_write_locked',
        finished_at: null,
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByText('Localized project write lock')).toBeInTheDocument();
    expect(screen.queryByText(/This task is changing project files/)).not.toBeInTheDocument();
  });

  it('shows recovery context, child rollup, and opens a result path', async () => {
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        status: 'interrupted',
        checkpoint: {
          available: true,
          resume_supported: true,
          stage: 'batch-4',
          updated_at: '2026-07-22T00:00:08Z',
        },
        result: {
          types: ['files', 'workflow_log'],
          output_paths: ['C:/Remis/output/incremental_update.log'],
          summary: '3 files processed',
        },
        child_aggregate: {
          total: 2,
          active: 1,
          attention: 0,
          completed: 1,
          progress: 70,
        },
        children: [
          { task_id: 'child-1', kind: 'repair', title: 'Repair', status: 'running' },
          { task_id: 'child-2', kind: 'repair', title: 'Repair', status: 'completed' },
        ],
      },
    });
    api.post.mockResolvedValue({ data: { status: 'success' } });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByText('batch-4')).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {
      name: 'button_open_folder: C:/Remis/output/incremental_update.log',
    }));
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/system/open_folder', {
        path: 'C:/Remis/output/incremental_update.log',
      });
    });
  });

  it('polls an active task to completion when the WebSocket stays silent', async () => {
    vi.useFakeTimers();
    taskIdParam = 'running-task';
    const runningTask = {
      ...failedTask,
      task_id: 'running-task',
      title: 'Running translation',
      status: 'running',
      finished_at: null,
      attention_reason: null,
      events: [],
    };
    api.get
      .mockResolvedValueOnce({ data: runningTask })
      .mockResolvedValue({ data: { ...runningTask, status: 'completed', progress: 100 } });

    class SilentWebSocket {
      close = vi.fn();
    }
    vi.stubGlobal('WebSocket', SilentWebSocket);

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(api.get).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(4000);
      vi.advanceTimersByTime(200);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(api.get).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0);
  });

  it('refreshes an active task when the page becomes visible again', async () => {
    taskIdParam = 'visible-task';
    const runningTask = {
      ...failedTask,
      task_id: 'visible-task',
      title: 'Visible task',
      status: 'running',
      finished_at: null,
      attention_reason: null,
      events: [],
    };
    api.get
      .mockResolvedValueOnce({ data: runningTask })
      .mockResolvedValue({ data: { ...runningTask, status: 'completed', progress: 100 } });

    const webSocketConnected = vi.fn();
    class SilentWebSocket {
      constructor() {
        webSocketConnected();
      }

      close = vi.fn();
    }
    vi.stubGlobal('WebSocket', SilentWebSocket);
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(webSocketConnected).toHaveBeenCalledTimes(1));

    document.dispatchEvent(new Event('visibilitychange'));

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0);
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
    expect(screen.getByText('glossary_health_penalty_error')).toBeInTheDocument();
    expect(screen.queryByText('Glossary health score 81/100.')).not.toBeInTheDocument();
    expect(screen.queryByText('Source and translation placeholders differ')).not.toBeInTheDocument();
    expect(screen.getByText('glossary_health_read_only')).toBeInTheDocument();
    expect(screen.queryByTestId('glossary-health-workbench')).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Review and fix issues' }));
    expect(navigateMock).toHaveBeenCalledWith('/tasks/health-task/glossary-health');

    fireEvent.click(screen.getByRole('button', { name: 'task_detail.back_to_workflow' }));
    expect(navigateMock).toHaveBeenCalledWith('/glossary-manager', {
      state: {
        projectId: 'project-demo',
        taskId: 'health-task',
      },
    });
  });

  it('returns an incremental run to the exact project and task mode', async () => {
    taskIdParam = 'incremental-task';
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        task_id: 'incremental-task',
        kind: 'incremental_translation',
        source_route: '/incremental-translation',
        workflow_context: { mode: 'pre_scan', project_id: 'project-demo' },
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'task_detail.back_to_workflow' }));

    expect(navigateMock).toHaveBeenCalledWith('/incremental-translation', {
      state: {
        projectId: 'project-demo',
        taskId: 'incremental-task',
        taskMode: 'pre_scan',
      },
    });
  });

  it('opens proofreading with the completed task identity preserved', async () => {
    taskIdParam = 'incremental-completed';
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        task_id: 'incremental-completed',
        kind: 'incremental_translation',
        status: 'completed',
        progress: 100,
        attention_reason: null,
        result: {
          types: ['files'],
          summary: '2 files processed',
          output_paths: ['C:/outputs/incremental'],
        },
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    fireEvent.click(await screen.findByRole('button', {
      name: 'project_management.primary_continue_proofreading',
    }));

    expect(navigateMock).toHaveBeenCalledWith(
      '/proofreading?projectId=project-demo&taskId=incremental-completed',
    );
    expect(screen.getByTestId('task-event-log')).not.toHaveAttribute('open');
  });

  it('keeps partial glossary results actionable and hides provider payload by default', async () => {
    taskIdParam = 'partial-health-task';
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        task_id: 'partial-health-task',
        kind: 'glossary_health_check',
        status: 'failed',
        message: 'provider payload: {"error":"No models loaded"}',
        attention_reason: 'provider payload: {"error":"No models loaded"}',
        source_route: '/glossary',
        result: {
          types: ['glossary_health_report'],
          summary: 'Deterministic checks completed, but advisory model review failed.',
          metadata: {
            score: 94,
            issue_count: 1,
            mutations_applied: false,
            ai_review_status: 'failed',
            ai_review_error: 'provider payload: {"error":"No models loaded"}',
            issues: [{
              code: 'placeholder_mismatch',
              severity: 'error',
              count: 1,
              items: [{ entry_id: 'token-a', glossary_id: 7 }],
            }],
          },
          },
        events: [{
          event_id: 'event-provider-error',
          level: 'error',
          message: 'provider payload: {"error":"No models loaded"}',
        }],
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByText('Partially completed')).toBeInTheDocument();
    expect(screen.getByText('Deterministic report available; AI advice unavailable.')).toBeInTheDocument();
    expect(screen.getByText('AI advice unavailable event')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review and fix issues' })).toBeInTheDocument();
    expect(screen.getByText(/provider payload/i)).not.toBeVisible();

    fireEvent.click(screen.getAllByText('task_detail.technical_info').at(-1));
    expect(screen.getByText(/provider payload/i)).toBeVisible();
  });

  it('localizes known legacy glossary inspection events and preserves unknown events', async () => {
    taskIdParam = 'legacy-health-task';
    api.get.mockResolvedValue({
      data: {
        ...failedTask,
        task_id: 'legacy-health-task',
        kind: 'glossary_health_check',
        status: 'completed',
        attention_reason: null,
        result: {
          types: ['glossary_health_report'],
          metadata: { score: 97, issue_count: 1, issues: [] },
        },
        events: [
          { event_id: 'queued', level: 'info', message: 'Glossary health check queued.' },
          { event_id: 'started', level: 'info', message: 'Deterministic glossary checks started.' },
          { event_id: 'found', level: 'info', message: 'Deterministic checks found 1 issue(s).' },
          { event_id: 'ai', level: 'info', message: 'Explicitly approved advisory model review started.' },
          { event_id: 'completed', level: 'info', message: 'Health report completed without changing glossary data.' },
          { event_id: 'unknown', level: 'info', message: 'Custom diagnostic event.' },
        ],
      },
    });

    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findByText('Localized inspection queued')).toBeInTheDocument();
    expect(screen.getByText('Localized deterministic checks started')).toBeInTheDocument();
    expect(screen.getByText('Localized 1 findings')).toBeInTheDocument();
    expect(screen.getByText('Localized AI advice started')).toBeInTheDocument();
    expect(screen.getByText('Localized inspection completed')).toBeInTheDocument();
    expect(screen.getByText('Custom diagnostic event.')).toBeInTheDocument();
    expect(screen.queryByText('Glossary health check queued.')).not.toBeInTheDocument();
  });
});

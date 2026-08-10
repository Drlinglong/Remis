import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HomePage from './HomePage';
import api from '../utils/api';

const navigateMock = vi.fn();
const startTourMock = vi.fn();
const setPageContextMock = vi.fn();
const refreshTasksMock = vi.fn();
let taskCenterState;

vi.mock('@mantine/core', async () => {
  const actual = await vi.importActual('@mantine/core');
  return {
    ...actual,
    Modal: ({ opened, children, title }) =>
      opened ? (
        <div>
          <div>{title}</div>
          {children}
        </div>
      ) : null,
    ScrollArea: ({ children }) => <div>{children}</div>,
  };
});

const { MantineProvider } = await import('@mantine/core');

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    startTour: startTourMock,
    setPageContext: setPageContextMock,
  }),
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
}));

vi.mock('../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => taskCenterState,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => {
      if (options?.returnObjects && key === 'homepage_slogans') {
        return ['Keep translating'];
      }
      if (options?.returnObjects && key === 'homepage_greetings') {
        return {
          morning: ['Good Morning'],
          afternoon: ['Good Afternoon'],
          evening: ['Good Evening'],
        };
      }
      return key;
    },
    i18n: {
      language: 'en',
    },
  }),
}));

vi.mock('../components/ProjectStatusPieChart', () => ({
  default: ({ data }) => <div data-testid="project-status-chart">{data.length}</div>,
}));

vi.mock('../components/ProjectDistributionPieChart', () => ({
  default: ({ data }) => <div data-testid="project-distribution-chart">{data.length}</div>,
}));

vi.mock('../components/GlossaryAnalysisBarChart', () => ({
  default: ({ data }) => <div data-testid="glossary-chart">{data.length}</div>,
}));

vi.mock('../components/RecentActivityList', () => ({
  default: ({ activities }) => <div data-testid="recent-activity">{activities.length}</div>,
}));

vi.mock('../components/StatCard', () => ({
  default: ({ title, value }) => (
    <div>
      <span>{title}</span>
      <span>{value}</span>
    </div>
  ),
}));

vi.mock('../components/ActionCard', () => ({
  default: () => <div />,
}));

vi.mock('../components/tasks/TaskSummaryCard', () => ({
  TaskSummaryCard: ({ task, onHandle, onOpen }) => (
    <div>
      <button type="button" onClick={() => onOpen(task)}>{task.title}</button>
      {onHandle && task.allowed_actions?.includes('archive_task') && (
        <button type="button" onClick={() => onHandle(task)}>task_center.mark_handled</button>
      )}
    </div>
  ),
}));

const renderWithProvider = (ui) =>
  render(<MantineProvider>{ui}</MantineProvider>);

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    taskCenterState = {
      activeCount: 0,
      attentionCount: 0,
      loading: false,
      refreshTasks: refreshTasksMock,
      tasks: [],
    };
    api.get.mockResolvedValue({
      data: {
        stats: {
          total_projects: 3,
          words_translated: 1200,
          active_tasks: 2,
          active_projects: 2,
          completion_rate: 50,
        },
        charts: {
          project_status: [{ name: 'active', value: 1 }],
          glossary_analysis: [{ name: 'terms', value: 10 }],
          project_distribution: [{ name: 'vic3', value: 3 }],
        },
        recent_activity: [{ id: 1 }],
      },
    });
  });

  it('loads dashboard data, sets page context, and navigates from the state-driven CTA', async () => {
    renderWithProvider(<HomePage />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/system/stats');
    });
    await screen.findByText('homepage_live_work_title');

    expect(setPageContextMock).toHaveBeenCalledWith(expect.any(Function));
    expect(setPageContextMock.mock.calls[0][0]('other')).toBe('home');
    expect(screen.queryByText('tutorial.auto_start_prompt.title')).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'homepage_action_continue_project' })[0]).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'homepage_action_continue_project' })[0]);
    expect(navigateMock).toHaveBeenCalledWith('/project-management');
    expect(startTourMock).not.toHaveBeenCalled();
  });

  it('keeps task operations inside the live-work area', async () => {
    taskCenterState = {
      ...taskCenterState,
      activeCount: 1,
      tasks: [{
        task_id: 'task-1',
        title: 'Translation',
        status: 'failed',
        allowed_actions: ['archive_task'],
      }],
    };
    api.post.mockResolvedValue({ data: {} });

    renderWithProvider(<HomePage />);

    expect(await screen.findByRole('button', { name: 'task_center.view_history' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'button_refresh' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'task_center.title' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'homepage_action_review_tasks' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'task_center.mark_handled' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/tasks/task-1/archive');
      expect(refreshTasksMock).toHaveBeenCalledWith({ quiet: true });
    });
  });

  it('uses the surface contrast contract for the dark live-work card', async () => {
    renderWithProvider(<HomePage />);

    const subtitle = await screen.findByText('homepage_live_work_subtitle');
    expect(subtitle.closest('.mantine-Card-root')).toHaveAttribute('data-remis-surface', 'surface');
  });

  it('uses readable paper tokens for the attention alert', async () => {
    taskCenterState = {
      ...taskCenterState,
      attentionCount: 2,
    };
    renderWithProvider(<HomePage />);

    const message = await screen.findByText('task_center.attention_summary');
    const alert = message.closest('.mantine-Alert-root');
    expect(alert).toHaveAttribute('data-remis-surface', 'paper');
    expect(alert.querySelector('.mantine-Alert-message')).toContainElement(message);
  });

  it('keeps the latest completed task visible and opens its exact task record', async () => {
    taskCenterState = {
      ...taskCenterState,
      tasks: [
        { task_id: 'task-running', title: 'Running translation', status: 'running' },
        { task_id: 'task-completed', title: 'Completed translation', status: 'completed' },
      ],
    };

    renderWithProvider(<HomePage />);

    const completedTask = await screen.findByRole('button', { name: 'Completed translation' });
    fireEvent.click(completedTask);

    expect(navigateMock).toHaveBeenCalledWith('/tasks/task-completed');
  });
});

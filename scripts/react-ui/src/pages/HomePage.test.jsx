import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HomePage from './HomePage';
import api from '../utils/api';

const navigateMock = vi.fn();
const startTourMock = vi.fn();
const setPageContextMock = vi.fn();
const openTaskCenterMock = vi.fn();
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
  },
}));

vi.mock('react-router-dom', () => ({
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
  TaskSummaryCard: ({ task }) => <div>{task.title}</div>,
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
      openTaskCenter: openTaskCenterMock,
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

  it('foregrounds the task center when work is already running', async () => {
    taskCenterState = {
      ...taskCenterState,
      activeCount: 1,
      tasks: [{ task_id: 'task-1', title: 'Translation', status: 'running' }],
    };

    renderWithProvider(<HomePage />);

    await waitFor(() => {
      expect(screen.getByText('homepage_action_view_tasks')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'homepage_action_view_tasks' }));
    expect(openTaskCenterMock).toHaveBeenCalledOnce();
  });
});

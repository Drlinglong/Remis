import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import HomeLiveWorkSection from './HomeLiveWorkSection';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('../../components/tasks/TaskSummaryCard', () => ({
  TaskSummaryCard: ({ task, onHandle, onOpen }) => (
    <div data-testid={`task-${task.task_id}`}>
      <button type="button" onClick={() => onOpen(task)}>{task.title || task.task_id}</button>
      {onHandle && task.allowed_actions?.includes('archive_task') && (
        <button type="button" onClick={() => onHandle(task)}>handle</button>
      )}
    </div>
  ),
}));

const translate = (key, options) => options?.defaultValue || key;
const renderSection = (workflow) => render(
  <MantineProvider>
    <HomeLiveWorkSection t={translate} workflow={workflow} />
  </MantineProvider>,
);

const baseWorkflow = {
  attentionCount: 0,
  handleError: '',
  handleErrorTaskId: '',
  handlingTaskId: '',
  markHandled: vi.fn(),
  openProjectManagement: vi.fn(),
  openTask: vi.fn(),
  openTaskHistory: vi.fn(),
  primaryTask: null,
  refreshLiveWork: vi.fn(),
  tasksLoading: false,
  visibleTasks: [],
};

describe('HomeLiveWorkSection', () => {
  it('keeps the empty state to one primary action', () => {
    const workflow = { ...baseWorkflow };
    const { container } = renderSection(workflow);

    expect(container.querySelectorAll('[data-remis-anchor="live-work"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-remis-action="primary"]')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'homepage_action_continue_project' }));
    expect(workflow.openProjectManagement).toHaveBeenCalledTimes(1);
  });

  it('opens the highest-priority actionable task as the sole primary action', () => {
    const task = { task_id: 'task-running', title: 'Long running translation', status: 'running' };
    const workflow = { ...baseWorkflow, primaryTask: task, visibleTasks: [task] };
    renderSection(workflow);

    expect(screen.getByRole('button', { name: 'task_center.view_task' })).toBeInTheDocument();
    expect(document.querySelectorAll('[data-remis-action="primary"]')).toHaveLength(1);
    fireEvent.click(document.querySelector('[data-remis-action="primary"]'));
    expect(workflow.openTask).toHaveBeenCalledWith(task);
  });

  it('keeps loading and archive failures inside Live Work', () => {
    const loading = { ...baseWorkflow, tasksLoading: true };
    const { rerender } = renderSection(loading);
    expect(screen.getByLabelText('home-live-work-loading')).toBeInTheDocument();

    const failed = {
      ...baseWorkflow,
      handleError: 'archive unavailable',
      handleErrorTaskId: 'task-1',
      visibleTasks: [{ task_id: 'task-1', title: 'Task', status: 'failed' }],
    };
    rerender(
      <MantineProvider>
        <HomeLiveWorkSection t={translate} workflow={failed} />
      </MantineProvider>,
    );
    expect(screen.getByText('archive unavailable')).toBeInTheDocument();
    expect(screen.getByText('archive unavailable').closest('[data-remis-surface="paper"]')).toBeInTheDocument();
  });
});

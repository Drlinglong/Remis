import { describe, expect, it } from 'vitest';

import { taskDetailRoute, taskWorkflowTarget } from './taskRoutes';

describe('taskDetailRoute', () => {
  it('preserves the selected task identity in the route', () => {
    expect(taskDetailRoute('failed/task 1')).toBe('/tasks/failed%2Ftask%201');
    expect(taskDetailRoute('successful-task')).toBe('/tasks/successful-task');
  });
});

describe('taskWorkflowTarget', () => {
  it('returns an incremental task to its exact project and run mode', () => {
    expect(taskWorkflowTarget({
      task_id: 'incremental-1',
      project_id: 'project-1',
      source_route: '/incremental-translation',
      workflow_context: { mode: 'pre_scan' },
    })).toEqual({
      pathname: '/incremental-translation',
      state: {
        projectId: 'project-1',
        taskId: 'incremental-1',
        taskMode: 'pre_scan',
      },
    });
  });

  it('keeps the glossary compatibility route without inventing context', () => {
    expect(taskWorkflowTarget({ source_route: '/glossary' })).toEqual({
      pathname: '/glossary-manager',
      state: {},
    });
  });
});

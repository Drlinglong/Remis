import { describe, expect, it } from 'vitest';

import { taskDetailRoute } from './taskRoutes';

describe('taskDetailRoute', () => {
  it('preserves the selected task identity in the route', () => {
    expect(taskDetailRoute('failed/task 1')).toBe('/tasks/failed%2Ftask%201');
    expect(taskDetailRoute('successful-task')).toBe('/tasks/successful-task');
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ExecutionStep from './ExecutionStep';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => options?.defaultValue || key,
  }),
}));
vi.mock('../shared/BusyHeartbeat', () => ({ default: () => null }));
vi.mock('./TelemetrySummary', () => ({ default: () => null }));

describe('ExecutionStep workflow handoff', () => {
  it('offers the exact task and project proofreading after completion', () => {
    Element.prototype.scrollTo = vi.fn();
    const onViewTask = vi.fn();
    const onStartProofreading = vi.fn();

    render(
      <MantineProvider>
        <ExecutionStep
          progress={100}
          executing={false}
          progressInfo={{ stage_code: 'completed' }}
          logs={[]}
          finalSummary={{ output_dir: 'C:/output', warning_count: 0 }}
          logViewportRef={{ current: null }}
          logScrollRef={{ current: null }}
          openOutputFolder={vi.fn()}
          handleFinish={vi.fn()}
          completionSource="polling"
          onViewTask={onViewTask}
          onStartProofreading={onStartProofreading}
        />
      </MantineProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'task_center.view_task' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.primary_continue_proofreading' }));

    expect(onViewTask).toHaveBeenCalledOnce();
    expect(onStartProofreading).toHaveBeenCalledOnce();
  });
});

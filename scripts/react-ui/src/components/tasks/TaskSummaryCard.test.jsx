import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TaskSummaryCard } from './TaskSummaryCard';

const translateMock = (key, options) => options?.defaultValue || key;

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: translateMock }),
}));

const { MantineProvider } = await import('@mantine/core');

describe('TaskSummaryCard', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('ticks the elapsed time while the task is active', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-22T00:00:05Z'));

    render(
      <MantineProvider>
        <TaskSummaryCard
          task={{
            task_id: 'running-task',
            kind: 'initial_translation',
            title: 'Running task',
            status: 'running',
            progress: 20,
            started_at: '2026-07-22T00:00:00Z',
            created_by: { type: 'user' },
          }}
          onOpen={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('00:00:05')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByText('00:00:06')).toBeInTheDocument();
  });
});

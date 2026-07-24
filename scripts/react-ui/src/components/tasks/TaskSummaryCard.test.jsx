import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TaskSummaryCard } from './TaskSummaryCard';

const translations = {
  'task_center.kind.glossary_health_check': '词典健康检查',
  'task_center.status.failed': '失败',
  glossary_health_no_model_loaded: '所选本地提供商尚未加载模型。',
};
const translateMock = (key, options) => translations[key] || options?.defaultValue || key;

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

  it('localizes glossary health task identity and known local-model failures', () => {
    render(
      <MantineProvider>
        <TaskSummaryCard
          task={{
            task_id: 'health-task',
            kind: 'glossary_health_check',
            title: 'Check 1 glossary asset(s)',
            status: 'failed',
            message: 'Model request failed: No models loaded. Please load a model.',
            created_by: { type: 'user' },
          }}
          onOpen={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('词典健康检查')).toBeInTheDocument();
    expect(screen.getByText('失败')).toBeInTheDocument();
    expect(screen.getByText('所选本地提供商尚未加载模型。')).toBeInTheDocument();
    expect(screen.queryByText('Check 1 glossary asset(s)')).not.toBeInTheDocument();
  });
});

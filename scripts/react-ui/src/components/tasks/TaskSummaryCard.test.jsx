import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TaskSummaryCard } from './TaskSummaryCard';

const translations = {
  'task_center.kind.agent_workshop': 'Format Repair',
  'task_center.creator.remis_agent': 'Remis Agent',
  'task_center.created_by': 'Created by {{creator}}',
  'task_center.kind.glossary_health_check': '词典健康检查',
  'task_center.status.failed': '失败',
  glossary_health_no_model_loaded: '所选本地提供商尚未加载模型。',
  glossary_health_partial_status: '部分完成',
  glossary_health_partial_message: '确定性健康检查已完成；可选 AI 建议暂不可用。',
  'task_presentation.provider_failure.invalid_model.title': '所选模型无效或不可用',
};
const translateMock = (key, options) => (
  (translations[key] || options?.defaultValue || key)
    .replace('{{creator}}', options?.creator || '')
);

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

  it('uses the shared paper surface contrast contract', () => {
    const { container } = render(
      <MantineProvider>
        <TaskSummaryCard
          task={{
            task_id: 'paper-surface-task',
            kind: 'initial_translation',
            title: 'Paper surface task',
            status: 'completed',
            allowed_actions: ['archive_task'],
            created_by: { type: 'user' },
          }}
          onHandle={vi.fn()}
          onOpen={vi.fn()}
        />
      </MantineProvider>,
    );

    const paper = container.querySelector('[data-remis-task-summary="true"]');
    expect(paper).toHaveAttribute('data-remis-surface', 'paper');
    expect(container.querySelector('[data-remis-surface="surface"]')).not.toBeInTheDocument();
    expect(paper.querySelectorAll('[data-remis-action="paper-secondary"]')).toHaveLength(2);
    expect(paper.querySelector('[data-remis-action="secondary"]')).not.toBeInTheDocument();
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

  it('presents a preserved deterministic report as partial completion', () => {
    render(
      <MantineProvider>
        <TaskSummaryCard
          task={{
            task_id: 'health-task',
            kind: 'glossary_health_check',
            title: 'Check 1 glossary asset(s)',
            status: 'failed',
            message: 'provider payload: No models loaded',
            attention_reason: 'provider payload: No models loaded',
            result: {
              types: ['glossary_health_report'],
              metadata: { ai_review_status: 'failed', score: 94 },
            },
            created_by: { type: 'user' },
          }}
          onOpen={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('部分完成')).toBeInTheDocument();
    expect(screen.getByText('确定性健康检查已完成；可选 AI 建议暂不可用。')).toBeInTheDocument();
    expect(screen.queryByText(/provider payload/i)).not.toBeInTheDocument();
  });

  it('shows Format Repair as distinct from the internal Remis Agent creator', () => {
    render(
      <MantineProvider>
        <TaskSummaryCard
          task={{
            task_id: 'format-repair-task',
            kind: 'agent_workshop',
            title: 'Legacy Agent Workshop title',
            status: 'completed',
            created_by: { type: 'remis_agent' },
          }}
          onOpen={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('Format Repair')).toBeInTheDocument();
    expect(screen.getByText('Created by Remis Agent')).toBeInTheDocument();
    expect(screen.queryByText('Legacy Agent Workshop title')).not.toBeInTheDocument();
  });

  it('shows an explicit invalid-model failure instead of a generic retry message', () => {
    render(
      <MantineProvider>
        <TaskSummaryCard
          task={{
            task_id: 'invalid-model-task',
            kind: 'initial_translation',
            title: 'Failed translation',
            status: 'failed',
            attention_reason: 'provider payload omitted',
            attention_reason_code: 'provider_invalid_model',
            created_by: { type: 'user' },
          }}
          onOpen={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('所选模型无效或不可用')).toBeInTheDocument();
    expect(screen.queryByText('provider payload omitted')).not.toBeInTheDocument();
  });
});

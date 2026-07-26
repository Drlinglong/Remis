import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ConfigStep from './ConfigStep';
import ExecutionStep from './ExecutionStep';
import PreScanResultsStep from './PreScanResultsStep';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => ({
      'incremental_translation.conflicting_task_title': '已有翻译任务',
      'incremental_translation.conflicting_task_notice': '打开现有任务查看进度',
      'incremental_translation.background_task_notice': '任务在后台运行，可以安全离开页面',
      'task_center.view_task': '查看任务',
    }[key] || key),
  }),
}));

const renderWithMantine = (component) => render(
  <MantineProvider>
    {component}
  </MantineProvider>,
);

describe('incremental task feedback', () => {
  it('explains why pre-scan is blocked and opens the exact existing task', () => {
    const onViewTask = vi.fn();

    renderWithMantine(
      <ConfigStep
        archiveInfo={{ project_name: 'Demo', archived_languages: ['zh-cn'] }}
        selectedProject={{
          project_id: 'project-1',
          name: 'Demo',
          game_id: 'stellaris',
          source_language: 'en',
          source_path: 'C:\\mods\\demo',
        }}
        selectedLangs={['zh-cn']}
        setSelectedLangs={vi.fn()}
        models={[]}
        apiProviders={[]}
        loading={false}
        conflictingTaskId="task-existing"
        currentTaskId="task-existing"
        onViewTask={onViewTask}
        onBack={vi.fn()}
        runPreScan={vi.fn()}
      />,
    );

    expect(screen.getByText('已有翻译任务')).toBeInTheDocument();
    expect(screen.getByText('打开现有任务查看进度')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'incremental_translation.run_pre_scan' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '查看任务' }));
    expect(onViewTask).toHaveBeenCalledOnce();
  });

  it('states that a running task survives navigation and exposes Task Center detail', () => {
    Element.prototype.scrollTo = vi.fn();
    const onViewTask = vi.fn();

    renderWithMantine(
      <ExecutionStep
        progress={35}
        executing
        progressInfo={{ stage_code: 'translating_content' }}
        logs={[]}
        finalSummary={null}
        logViewportRef={{ current: null }}
        logScrollRef={{ current: null }}
        onViewTask={onViewTask}
      />,
    );

    expect(screen.getByText('任务在后台运行，可以安全离开页面')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看任务' }));
    expect(onViewTask).toHaveBeenCalledOnce();
  });

  it('explains a disabled execution button and opens the active task', () => {
    const onViewTask = vi.fn();

    renderWithMantine(
      <PreScanResultsStep
        scanResults={{
          total: 1,
          changed: 1,
          file_summaries: [],
        }}
        selectedProject={{ source_language: 'zh-CN' }}
        selectedLangs={['en']}
        models={[]}
        apiProviders={[]}
        archiveInfo={{ archived_languages: ['en'] }}
        loading={false}
        executing
        currentTaskId="task-running"
        onViewTask={onViewTask}
      />,
    );

    expect(screen.getByText('已有翻译任务')).toBeInTheDocument();
    expect(screen.getByText('打开现有任务查看进度')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'incremental_translation.step_4_title' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '查看任务' }));
    expect(onViewTask).toHaveBeenCalledOnce();
  });

  it('keeps a duplicate execution conflict visible with an exact task entry', () => {
    const onViewTask = vi.fn();

    renderWithMantine(
      <ExecutionStep
        progress={0}
        executing={false}
        progressInfo={{ stage_code: 'initializing' }}
        logs={[]}
        finalSummary={null}
        conflictingTaskId="task-existing"
        logViewportRef={{ current: null }}
        logScrollRef={{ current: null }}
        onViewTask={onViewTask}
      />,
    );

    expect(screen.getByText('已有翻译任务')).toBeInTheDocument();
    expect(screen.getByText('打开现有任务查看进度')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看任务' }));
    expect(onViewTask).toHaveBeenCalledOnce();
  });
});

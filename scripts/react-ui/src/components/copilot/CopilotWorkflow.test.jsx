import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import InlineLocalizationWorkflow from './InlineLocalizationWorkflow';
import RemisCopilotThread from './RemisCopilotThread';
import {
  executeGuidedLocalizationWorkflow,
  executeInitialTranslationWorkflow,
  fetchCopilotSettings,
  planInitialTranslationWorkflow,
  planLocalizationWorkflow,
} from '../../services/copilotService';
import projectService from '../../services/projectService';

const mocks = vi.hoisted(() => ({
  append: vi.fn(),
  setActiveStep: vi.fn(),
  setIsProcessing: vi.fn(),
  setSelectedProjectId: vi.fn(),
  setTaskId: vi.fn(),
  setTranslationDetails: vi.fn(),
  threadIsRunning: false,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_key, fallback) => fallback || _key }),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));

vi.mock('../../services/copilotService', () => ({
  executeGuidedLocalizationWorkflow: vi.fn(),
  executeInitialTranslationWorkflow: vi.fn(),
  fetchCopilotSettings: vi.fn(),
  planInitialTranslationWorkflow: vi.fn(),
  planLocalizationWorkflow: vi.fn(),
  sendCopilotChat: vi.fn(),
}));

vi.mock('../../services/projectService', () => ({
  default: { getActiveProjects: vi.fn() },
}));

vi.mock('../../hooks/useCopilotActions', () => ({
  useCopilotActions: () => ({ runAction: vi.fn() }),
}));

vi.mock('../../context/TranslationContextCore', () => ({
  useTranslationContext: () => ({
    setActiveStep: mocks.setActiveStep,
    setIsProcessing: mocks.setIsProcessing,
    setSelectedProjectId: mocks.setSelectedProjectId,
    setTaskId: mocks.setTaskId,
    setTranslationDetails: mocks.setTranslationDetails,
  }),
}));

vi.mock('@assistant-ui/react', async () => {
  const ReactModule = await import('react');
  const passthrough = ({ children }) => ReactModule.createElement(ReactModule.Fragment, null, children);
  const message = {
    role: 'assistant',
    metadata: {
      custom: {
        suggested_actions: [{
          action: 'start_localization_workflow',
          label: '开始汉化',
          args: { folder_path: 'J:/mods/demo' },
        }],
      },
    },
  };

  return {
    AssistantRuntimeProvider: passthrough,
    ComposerPrimitive: {
      Root: passthrough,
      Input: (props) => ReactModule.createElement('textarea', props),
      Send: passthrough,
    },
    MessagePrimitive: {
      Root: passthrough,
      Parts: () => null,
    },
    ThreadPrimitive: {
      Root: passthrough,
      Viewport: passthrough,
      Empty: () => null,
      Messages: ({ components }) => ReactModule.createElement(components.AssistantMessage),
    },
    useLocalRuntime: () => ({ thread: { append: mocks.append } }),
    useMessage: (selector) => selector(message),
    useThread: (selector) => selector({ messages: [], isRunning: mocks.threadIsRunning }),
  };
});

const renderWithMantine = (ui) => render(<MantineProvider>{ui}</MantineProvider>);

describe('Copilot localization workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.threadIsRunning = false;
    fetchCopilotSettings.mockResolvedValue({
      settings: { provider: 'lm_studio', model: 'local-model' },
      providers: [{ id: 'lm_studio', name: 'LM Studio', models: ['local-model'], default_model: 'local-model' }],
    });
    projectService.getActiveProjects.mockResolvedValue({ data: [] });
  });

  it('shows an accessible thinking indicator while the assistant run is active', () => {
    mocks.threadIsRunning = true;

    renderWithMantine(
      <RemisCopilotThread sessionId="session-thinking" onMessagesChange={vi.fn()} />,
    );

    expect(screen.getByRole('status', { name: '模型正在思考' })).toBeInTheDocument();
  });

  it('resolves an existing project, locks server-owned fields and allows multiple targets', async () => {
    projectService.getActiveProjects.mockResolvedValue({ data: [{
      project_id: 'project-existing',
      name: 'Existing Demo',
      source_path: 'J:/mods/existing',
      game_id: 'victoria3',
      source_language: 'en',
    }] });
    planInitialTranslationWorkflow.mockResolvedValue({
      plan_id: 'existing-plan',
      title: 'Ready',
      summary: 'Existing project inspected',
      inspection: { source_path: 'J:/mods/existing', project_file_count: 2 },
    });
    executeInitialTranslationWorkflow.mockResolvedValue({ task_id: 'existing-task' });
    const onStarted = vi.fn();

    renderWithMantine(
      <InlineLocalizationWorkflow
        initialArgs={{ project_name: 'Existing Demo', target_language: 'zh-CN' }}
        onStarted={onStarted}
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByDisplayValue('J:/mods/existing')).toHaveAttribute('readonly');
    expect(screen.getByDisplayValue('Existing Demo')).toHaveAttribute('readonly');
    expect(screen.getByDisplayValue('Victoria 3')).toHaveAttribute('readonly');
    expect(screen.getByDisplayValue('English')).toHaveAttribute('readonly');
    expect(screen.queryByRole('button', { name: '浏览' })).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText('目标语言')[0]);
    fireEvent.click(await screen.findByText('日本語'));
    fireEvent.click(screen.getByRole('button', { name: '只读检查并预览' }));

    await waitFor(() => expect(planInitialTranslationWorkflow).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 'project-existing',
      target_lang_codes: ['zh-CN', 'ja'],
    })));
    fireEvent.click(await screen.findByRole('button', { name: '批准并启动翻译' }));
    await waitFor(() => expect(executeInitialTranslationWorkflow).toHaveBeenCalledWith('existing-plan'));
    expect(onStarted).toHaveBeenCalledWith(expect.objectContaining({
      projectId: 'project-existing',
      taskId: 'existing-task',
      targetLanguages: ['zh-CN', 'ja'],
    }));
    expect(executeGuidedLocalizationWorkflow).not.toHaveBeenCalled();
  });

  it('shows the persisted source language and blocks selecting it as a target', async () => {
    projectService.getActiveProjects.mockResolvedValue({ data: [{
      project_id: 'project-zh',
      name: 'Chinese Source Demo',
      source_path: 'J:/mods/chinese-source',
      game_id: 'victoria3',
      source_language: 'zh-CN',
    }] });

    renderWithMantine(
      <InlineLocalizationWorkflow
        initialArgs={{ project_name: 'Chinese Source Demo', target_language: 'zh-CN' }}
        onStarted={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByDisplayValue('简体中文')).toHaveAttribute('readonly');
    expect(screen.getByText(/不能同时作为目标语言/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '只读检查并预览' })).toBeDisabled();
    expect(planInitialTranslationWorkflow).not.toHaveBeenCalled();
  });

  it('requires preview before approval and emits the started workflow metadata', async () => {
    planLocalizationWorkflow.mockResolvedValue({
      plan_id: 'plan-1',
      title: 'Ready',
      summary: 'Two files found',
      inspection: { folder_path: 'J:/mods/demo', localization_file_count: 2 },
    });
    executeGuidedLocalizationWorkflow.mockResolvedValue({
      task_id: 'task-1',
      project: { project_id: 'project-1', name: 'Demo Mod' },
    });
    const onStarted = vi.fn();

    renderWithMantine(
      <InlineLocalizationWorkflow
        initialArgs={{ folder_path: 'J:/mods/demo', project_name: 'Demo Mod' }}
        onStarted={onStarted}
        onClose={vi.fn()}
      />,
    );

    expect(executeGuidedLocalizationWorkflow).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '只读检查并预览' }));

    expect(await screen.findByText('Two files found')).toBeInTheDocument();
    expect(planLocalizationWorkflow).toHaveBeenCalledWith(expect.objectContaining({
      folder_path: 'J:/mods/demo',
      project_name: 'Demo Mod',
    }));
    expect(executeGuidedLocalizationWorkflow).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '批准并启动翻译' }));

    await waitFor(() => expect(executeGuidedLocalizationWorkflow).toHaveBeenCalledWith('plan-1'));
    expect(onStarted).toHaveBeenCalledWith(expect.objectContaining({
      taskId: 'task-1',
      projectId: 'project-1',
      projectName: 'Demo Mod',
      sourceLanguage: 'en',
      targetLanguage: 'zh-CN',
    }));
  });

  it('writes an approved workflow into translation state and chat history', async () => {
    renderWithMantine(
      <RemisCopilotThread sessionId="session-1" onMessagesChange={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole('button', { name: '开始汉化' }));
    expect(await screen.findByText('在对话中规划汉化')).toBeInTheDocument();

    planLocalizationWorkflow.mockResolvedValue({
      plan_id: 'plan-2',
      title: 'Ready',
      summary: 'One file found',
      inspection: { folder_path: 'J:/mods/demo', localization_file_count: 1 },
    });
    executeGuidedLocalizationWorkflow.mockResolvedValue({
      task_id: 'task-2',
      project: { project_id: 'project-2', name: 'Copilot Demo' },
    });

    fireEvent.click(screen.getByRole('button', { name: '只读检查并预览' }));
    await screen.findByText('One file found');
    fireEvent.click(screen.getByRole('button', { name: '批准并启动翻译' }));

    await waitFor(() => expect(mocks.setTaskId).toHaveBeenCalledWith('task-2'));
    expect(mocks.setSelectedProjectId).toHaveBeenCalledWith('project-2');
    expect(mocks.setIsProcessing).toHaveBeenCalledWith(true);
    expect(mocks.setActiveStep).toHaveBeenCalledWith(2);
    expect(mocks.setTranslationDetails).toHaveBeenCalledWith(expect.objectContaining({
      projectId: 'project-2',
      modName: 'Copilot Demo',
    }));
    expect(mocks.append).toHaveBeenCalledWith(expect.objectContaining({
      role: 'assistant',
      metadata: expect.objectContaining({
        custom: expect.objectContaining({
          workflow: expect.objectContaining({ taskId: 'task-2', projectId: 'project-2' }),
        }),
      }),
    }));
  });

  it('invalidates a stale approval card and regenerates only a fresh read-only preview', async () => {
    planLocalizationWorkflow
      .mockResolvedValueOnce({
        plan_id: 'stale-plan',
        title: 'Old ready plan',
        summary: 'Old scan',
        inspection: { folder_path: 'J:/mods/demo', localization_file_count: 1 },
      })
      .mockResolvedValueOnce({
        plan_id: 'fresh-plan',
        title: 'Fresh ready plan',
        summary: 'Fresh scan',
        inspection: { folder_path: 'J:/mods/demo', localization_file_count: 2 },
      });
    executeGuidedLocalizationWorkflow.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: { code: 'workflow_plan_stale', message: 'Plan changed' } },
      },
    });

    renderWithMantine(
      <InlineLocalizationWorkflow
        initialArgs={{ folder_path: 'J:/mods/demo', project_name: 'Demo Mod' }}
        onStarted={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '只读检查并预览' }));
    expect(await screen.findByText('Old scan')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '批准并启动翻译' }));

    expect(await screen.findByText('预览已失效，不能批准')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '批准并启动翻译' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重新检查并生成预览' }));

    await waitFor(() => expect(planLocalizationWorkflow).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Fresh scan')).toBeInTheDocument();
    expect(screen.queryByText('预览已失效，不能批准')).not.toBeInTheDocument();
    expect(executeGuidedLocalizationWorkflow).toHaveBeenCalledTimes(1);
  });

  it('reports project-created partial success and recovers through the existing project', async () => {
    planLocalizationWorkflow.mockResolvedValue({
      plan_id: 'guided-plan',
      title: 'Ready',
      summary: 'Create and translate',
      inspection: { folder_path: 'J:/mods/demo', localization_file_count: 1 },
    });
    executeGuidedLocalizationWorkflow.mockResolvedValue({
      code: 'project_created_translation_not_started',
      workflow_status: 'project_created_translation_not_started',
      partial_success: true,
      project: {
        project_id: 'created-project',
        name: 'Demo Mod',
        source_path: 'J:/managed/demo',
        game_id: 'victoria3',
        source_language: 'en',
      },
    });
    planInitialTranslationWorkflow.mockResolvedValue({
      plan_id: 'recovery-plan',
      title: 'Recovery ready',
      summary: 'Existing project inspected',
      inspection: { source_path: 'J:/managed/demo', project_file_count: 1 },
    });
    const onStarted = vi.fn();
    const onRecoveryAction = vi.fn();

    renderWithMantine(
      <InlineLocalizationWorkflow
        initialArgs={{ folder_path: 'J:/mods/demo', project_name: 'Demo Mod' }}
        onStarted={onStarted}
        onRecoveryAction={onRecoveryAction}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '只读检查并预览' }));
    fireEvent.click(await screen.findByRole('button', { name: '批准并启动翻译' }));

    expect(await screen.findByText('项目已创建，但翻译尚未启动')).toBeInTheDocument();
    expect(onStarted).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '批准并启动翻译' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '打开已有项目' }));
    expect(onRecoveryAction).toHaveBeenCalledWith({
      action: 'open_initial_translation',
      args: { project_id: 'created-project' },
    });

    fireEvent.click(screen.getByRole('button', { name: '重新检查翻译参数' }));
    await waitFor(() => expect(planInitialTranslationWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 'created-project' }),
    ));
    expect(planLocalizationWorkflow).toHaveBeenCalledTimes(1);
  });
});

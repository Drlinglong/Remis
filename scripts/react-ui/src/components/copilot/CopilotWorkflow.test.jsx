import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import InlineLocalizationWorkflow from './InlineLocalizationWorkflow';
import RemisCopilotThread from './RemisCopilotThread';
import {
  executeGuidedLocalizationWorkflow,
  planLocalizationWorkflow,
} from '../../services/copilotService';

const mocks = vi.hoisted(() => ({
  append: vi.fn(),
  setActiveStep: vi.fn(),
  setIsProcessing: vi.fn(),
  setSelectedProjectId: vi.fn(),
  setTaskId: vi.fn(),
  setTranslationDetails: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_key, fallback) => fallback || _key }),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));

vi.mock('../../services/copilotService', () => ({
  executeGuidedLocalizationWorkflow: vi.fn(),
  planLocalizationWorkflow: vi.fn(),
  sendCopilotChat: vi.fn(),
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
    useThread: (selector) => selector({ messages: [] }),
  };
});

const renderWithMantine = (ui) => render(<MantineProvider>{ui}</MantineProvider>);

describe('Copilot localization workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});

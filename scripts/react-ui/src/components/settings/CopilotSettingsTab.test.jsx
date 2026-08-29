import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CopilotSettingsTab from './CopilotSettingsTab';
import { applyReasoningToggle } from './copilotSettingsForm';
import { fetchCopilotSettings, saveCopilotSettings } from '../../services/copilotService';

vi.mock('../../services/copilotService', () => ({
  fetchCopilotSettings: vi.fn(),
  saveCopilotSettings: vi.fn(),
}));

vi.mock('@mantine/notifications', () => ({ notifications: { show: vi.fn() } }));

describe('CopilotSettingsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchCopilotSettings.mockResolvedValue({
      settings: {
        provider: 'lm_studio', model: 'local-model', reasoning_enabled: false, reasoning_preset: 'medium',
      },
      providers: [
        { id: 'lm_studio', name: 'LM Studio', models: ['local-model'], default_model: 'local-model', reasoning_models: {} },
        {
          id: 'openai', name: 'OpenAI', models: ['gpt-5.6-luna'], default_model: 'gpt-5.6-luna',
          reasoning_models: { 'gpt-5.6-luna': { presets: { low: {}, high: {} } } },
        },
      ],
    });
    saveCopilotSettings.mockImplementation(async (payload) => ({ ...payload, reasoning: {} }));
  });

  it('saves one shared provider, model and reasoning strength', async () => {
    render(<MantineProvider><CopilotSettingsTab /></MantineProvider>);
    expect(await screen.findByText('小助手设置')).toBeInTheDocument();
    expect(screen.getByText(/200000 tokens/)).toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText('供应商')[0]);
    fireEvent.click(await screen.findByText('OpenAI'));
    fireEvent.click(screen.getByRole('switch', { name: /启用模型内置推理/ }));
    fireEvent.click(screen.getAllByLabelText('推理强度')[0]);
    fireEvent.click(await screen.findByText('高'));
    fireEvent.click(screen.getByRole('button', { name: '保存小助手设置' }));

    await waitFor(() => expect(saveCopilotSettings).toHaveBeenCalledWith({
      provider: 'openai',
      model: 'gpt-5.6-luna',
      reasoning_enabled: true,
      reasoning_preset: 'high',
    }));
  });

  it('captures the switch value before React clears currentTarget', () => {
    const event = { currentTarget: { checked: true } };
    let updater;

    applyReasoningToggle(event, (value) => { updater = value; }, ['low', 'high']);
    event.currentTarget = null;

    expect(updater({ reasoning_enabled: false, reasoning_preset: 'medium' })).toEqual({
      reasoning_enabled: true,
      reasoning_preset: 'low',
    });
  });
});

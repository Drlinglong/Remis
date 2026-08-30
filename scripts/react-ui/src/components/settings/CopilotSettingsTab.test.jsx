import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CopilotSettingsTab from './CopilotSettingsTab';
import { applyReasoningToggle } from './copilotSettingsForm';
import { fetchCopilotSettings, saveCopilotSettings } from '../../services/copilotService';
import { UnsavedChangesGuardProvider } from '../../hooks/useUnsavedChangesGuard';

vi.mock('../../services/copilotService', () => ({
  fetchCopilotSettings: vi.fn(),
  saveCopilotSettings: vi.fn(),
}));

vi.mock('@mantine/notifications', () => ({ notifications: { show: vi.fn() } }));

const LocationMarker = () => <div data-testid="location">{useLocation().pathname}</div>;

const renderGuarded = () => {
  const router = createMemoryRouter([
    {
      path: '/settings',
      element: (
        <UnsavedChangesGuardProvider>
          <CopilotSettingsTab />
        </UnsavedChangesGuardProvider>
      ),
    },
    { path: '/home', element: <LocationMarker /> },
  ], { initialEntries: ['/settings'] });
  render(<MantineProvider><RouterProvider router={router} /></MantineProvider>);
  return router;
};

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

  it('warns before route navigation and allows exactly the requested discard', async () => {
    const router = renderGuarded();
    expect(await screen.findByText('小助手设置')).toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText('供应商')[0]);
    fireEvent.click(await screen.findByText('OpenAI'));

    const beforeUnloadEvent = new Event('beforeunload', { cancelable: true });
    const preventDefault = vi.spyOn(beforeUnloadEvent, 'preventDefault');
    window.dispatchEvent(beforeUnloadEvent);
    expect(preventDefault).toHaveBeenCalled();

    router.navigate('/home');
    expect(await screen.findByRole('button', { name: '返回并检查' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '放弃改动并离开' }));
    expect(await screen.findByTestId('location')).toHaveTextContent('/home');
  });

  it('clears the dirty baseline after a successful save', async () => {
    renderGuarded();
    expect(await screen.findByText('小助手设置')).toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText('供应商')[0]);
    fireEvent.click(await screen.findByText('OpenAI'));
    fireEvent.click(screen.getByRole('button', { name: '保存小助手设置' }));
    await waitFor(() => expect(saveCopilotSettings).toHaveBeenCalled());

    const beforeUnloadEvent = new Event('beforeunload', { cancelable: true });
    const preventDefault = vi.spyOn(beforeUnloadEvent, 'preventDefault');
    window.dispatchEvent(beforeUnloadEvent);
    expect(preventDefault).not.toHaveBeenCalled();
  });
});

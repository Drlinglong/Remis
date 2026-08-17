import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import ApiSettingsTab from './ApiSettingsTab';
import api from '../utils/api';
import { notifications } from '@mantine/notifications';

// Mock dependencies
vi.mock('../utils/api', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

vi.mock('@mantine/notifications', () => ({
    notifications: {
        show: vi.fn(),
    },
}));

// Mock i18next
vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key) => key,
        i18n: {
            language: 'zh-CN',
            changeLanguage: vi.fn(),
        },
    }),
}));

const renderWithProvider = (ui) => {
    return render(
        <MantineProvider>
            {ui}
        </MantineProvider>
    );
};

describe('ApiSettingsTab Stability', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        api.get.mockResolvedValue({
            data: [
                { id: 'gemini', name: 'Gemini', has_key: false, description_key: 'api_desc_gemini' },
                { id: 'openrouter', name: 'OpenRouter', has_key: false, description_key: 'api_desc_openrouter' },
                { id: 'your_favourite_api', name: 'Custom', has_key: false, description_key: 'api_desc_custom' }
            ]
        });
    });

    it('renders and prevents ReferenceError crashes', async () => {
        renderWithProvider(<ApiSettingsTab />);

        // Wait for loader to disappear and component to render its structure
        await waitFor(() => {
            // Check for existing structural elements
            expect(screen.getByText(/api_settings_description/i)).toBeInTheDocument();
        }, { timeout: 3000 });

        // Check for groups
        expect(screen.getByText(/api_group_usa/i)).toBeInTheDocument();
        expect(screen.getByText(/api_group_china/i)).toBeInTheDocument();
        expect(screen.getByText('OpenRouter')).toBeInTheDocument();
        expect(screen.getByText('api_aventine_action')).toBeInTheDocument();
        expect(
            screen.getByText('api_aventine_title').closest('[data-remis-surface="paper"]'),
        ).not.toBeNull();
    });

    it('tests a local provider using the URL currently in the edit form', async () => {
        api.get.mockResolvedValue({
            data: [{
                id: 'lm_studio',
                name: 'LM Studio',
                is_keyless: true,
                api_url: 'http://localhost:1234/v1',
                selected_model: 'local-model',
                description_key: 'api_desc_lm_studio',
            }],
        });
        api.post.mockResolvedValue({ data: { status: 'success' } });

        renderWithProvider(<ApiSettingsTab />);
        await screen.findByText('LM Studio');
        fireEvent.click(screen.getByRole('button', { name: 'settings_api_label_configure' }));

        const urlInput = screen.getByDisplayValue('http://localhost:1234/v1');
        fireEvent.change(urlInput, { target: { value: 'http://127.0.0.1:6640/v1' } });
        fireEvent.click(screen.getByRole('button', { name: 'api_test_connection' }));

        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith('/api/providers/test-connection', {
                provider_id: 'lm_studio',
                api_url: 'http://127.0.0.1:6640/v1',
            });
        });
        expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
            message: 'api_connection_success',
            color: 'green',
        }));
    });

    it('accepts wrapped provider payloads without crashing the settings page', async () => {
        api.get.mockResolvedValue({
            data: {
                providers: [
                    { id: 'gemini', name: 'Gemini', has_key: false },
                    { id: 'your_favourite_api', name: 'Custom', has_key: false },
                ],
            },
        });

        renderWithProvider(<ApiSettingsTab />);

        expect(await screen.findByText('api_settings_description')).toBeInTheDocument();
        expect(screen.getByText('api_group_usa')).toBeInTheDocument();
    });

    it('falls back to an empty provider list for malformed payloads', async () => {
        api.get.mockResolvedValue({ data: { unexpected: true } });

        renderWithProvider(<ApiSettingsTab />);

        expect(await screen.findByText('api_settings_description')).toBeInTheDocument();
        expect(screen.getByText('api_group_local')).toBeInTheDocument();
    });

    it('saves verified reasoning controls and advanced custom JSON', async () => {
        api.get.mockResolvedValue({
            data: [{
                id: 'openai',
                name: 'OpenAI',
                selected_model: 'gpt-5.6-luna',
                available_models: ['gpt-5.6-luna'],
                reasoning: {
                    supported: true,
                    builtin_enabled: true,
                    selected_preset: 'low',
                    custom_parameters: {},
                },
                reasoning_models: {
                    'gpt-5.6-luna': {
                        presets: {
                            low: { reasoning_effort: 'low' },
                            high: { reasoning_effort: 'high' },
                        },
                    },
                },
            }],
        });
        api.post.mockResolvedValue({ data: { status: 'success' } });

        renderWithProvider(<ApiSettingsTab />);
        await screen.findByText('OpenAI');
        fireEvent.click(screen.getByRole('button', { name: 'settings_api_label_configure' }));
        fireEvent.change(screen.getByLabelText('api_custom_parameters_label'), {
            target: { value: '{"reasoning":{"exclude":true}}' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'save' }));

        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith('/api/providers/config', expect.objectContaining({
                provider_id: 'openai',
                reasoning_builtin_enabled: true,
                reasoning_preset: 'low',
                custom_parameters: { reasoning: { exclude: true } },
            }));
        });
    });
});

import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import ApiSettingsTab from './ApiSettingsTab';
import api from '../utils/api';

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
    });
});

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';
import AgentWorkshopPage from '../AgentWorkshopPage';
import axios from 'axios';

const setPageContextMock = vi.fn();
const startTourMock = vi.fn();

// Mock axios
vi.mock('axios');

// Polyfill ResizeObserver for Mantine
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserver;

// Mock i18next
vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key) => key,
    }),
}));

vi.mock('../../context/TutorialContext', () => ({
    useTutorial: () => ({
        setPageContext: setPageContextMock,
        startTour: startTourMock,
    }),
    getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
}));

const renderWithProvider = (ui) => {
    return render(
        <MantineProvider>
            <MemoryRouter>
                {ui}
            </MemoryRouter>
        </MantineProvider>
    );
};

describe('AgentWorkshopPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        
        // Mock Projects API
        axios.get.mockImplementation((url) => {
            if (url === '/api/projects') {
                return Promise.resolve({
                    data: [
                        { project_id: 'test-p', name: 'Test Project', game_id: 'vic3', status: 'active' }
                    ]
                });
            }
            if (url === '/api/config') {
                return Promise.resolve({
                    data: {
                        api_providers: [
                            { 
                                value: 'gemini', 
                                label: 'Gemini', 
                                available_models: ['gemini-pro'],
                                custom_models: ['custom-g'],
                                selected_model: 'gemini-pro'
                            }
                        ]
                    }
                });
            }
            return Promise.reject(new Error('not found'));
        });
    });

    it('renders and fetches config', async () => {
        renderWithProvider(<AgentWorkshopPage />);
        
        // Check for title
        expect(screen.getByText(/page_title_agent_workshop/i)).toBeInTheDocument();
        
        await waitFor(() => {
            expect(axios.get).toHaveBeenCalledWith('/api/config');
        });

        expect(setPageContextMock).toHaveBeenCalledWith(expect.any(Function));
    });

    it('handles missing available_models gracefully', async () => {
        axios.get.mockImplementation((url) => {
            if (url === '/api/config') {
                return Promise.resolve({
                    data: {
                        api_providers: [
                            { value: 'empty', label: 'Empty Provider' } // No models
                        ]
                    }
                });
            }
            return Promise.resolve({ data: [] });
        });

        renderWithProvider(<AgentWorkshopPage />);
        
        await waitFor(() => {
            expect(axios.get).toHaveBeenCalledWith('/api/config');
            expect(screen.getByText(/page_title_agent_workshop/i)).toBeInTheDocument();
        });
    });
});

import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';
import AgentWorkshopPage from '../AgentWorkshopPage';
import api from '../../utils/api';
import { AGENT_WORKSHOP_STORAGE_KEY } from '../../hooks/agentWorkshopSession';

const setPageContextMock = vi.fn();
const startTourMock = vi.fn();

vi.mock('../../utils/api', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

// Polyfill ResizeObserver for Mantine
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserver;
Object.defineProperty(window.HTMLElement.prototype, 'scrollTo', {
    configurable: true,
    value: vi.fn(),
});

// Mock i18next
vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key) => key,
    }),
}));

vi.mock('../../context/TutorialContextCore', () => ({
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
        sessionStorage.clear();
        
        // Mock Projects API
        api.get.mockImplementation((url) => {
            if (url === '/api/projects?status=active' || url === '/api/projects') {
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
            return Promise.resolve({ data: [] });
        });
    });

    it('renders and fetches config', async () => {
        renderWithProvider(<AgentWorkshopPage />);
        
        // Check for title
        expect(screen.getByText(/page_title_agent_workshop/i)).toBeInTheDocument();
        
        await waitFor(() => {
            expect(api.get).toHaveBeenCalledWith('/api/config');
        });

        expect(setPageContextMock).toHaveBeenCalledWith(expect.any(Function));
    });

    it('handles missing available_models gracefully', async () => {
        api.get.mockImplementation((url) => {
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
            expect(api.get).toHaveBeenCalledWith('/api/config');
            expect(screen.getByText(/page_title_agent_workshop/i)).toBeInTheDocument();
        });
    });

    it('keeps polling a restored run until completion', async () => {
        sessionStorage.setItem(AGENT_WORKSHOP_STORAGE_KEY, JSON.stringify({
            active: 3,
            selectedProjectId: 'test-p',
            selectedProvider: 'gemini',
            selectedModel: 'gemini-pro',
            issues: [{ file_name: 'file.yml', key: 'entry' }],
            fixedIssues: [],
            executionLogs: [],
            executing: true,
            currentRunTaskId: 'task-resume',
        }));

        let statusCalls = 0;
        api.get.mockImplementation((url) => {
            if (url === '/api/projects?status=active' || url === '/api/projects') {
                return Promise.resolve({
                    data: [{ project_id: 'test-p', name: 'Test Project', game_id: 'vic3', status: 'active' }],
                });
            }
            if (url === '/api/config') {
                return Promise.resolve({
                    data: {
                        api_providers: [{
                            value: 'gemini',
                            label: 'Gemini',
                            available_models: ['gemini-pro'],
                            selected_model: 'gemini-pro',
                        }],
                    },
                });
            }
            if (url === '/api/status/task-resume') {
                statusCalls += 1;
                return Promise.resolve({
                    data: statusCalls === 1
                        ? { status: 'running', progress: { percent: 40 }, log: ['running'] }
                        : {
                            status: 'completed',
                            progress: { percent: 100 },
                            log: ['done'],
                            summary: {
                                total: 1,
                                completed: 1,
                                successCount: 1,
                                failedCount: 0,
                                results: [{ file_name: 'file.yml', key: 'entry', status: 'SUCCESS' }],
                            },
                        },
                });
            }
            return Promise.resolve({ data: [] });
        });

        renderWithProvider(<AgentWorkshopPage />);

        await waitFor(() => {
            expect(api.get.mock.calls.filter(([url]) => url === '/api/status/task-resume')).toHaveLength(2);
        }, { timeout: 4000 });

        await waitFor(() => {
            const snapshot = JSON.parse(sessionStorage.getItem(AGENT_WORKSHOP_STORAGE_KEY));
            expect(snapshot.executing).toBe(false);
            expect(snapshot.currentRunTaskId).toBeNull();
        });
    }, 5000);
});

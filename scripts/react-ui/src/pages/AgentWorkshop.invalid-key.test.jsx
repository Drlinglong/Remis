import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AgentWorkshopPage from './AgentWorkshopPage';
import { AGENT_WORKSHOP_STORAGE_KEY } from '../hooks/agentWorkshopSession';
import api from '../utils/api';
import { notifications } from '@mantine/notifications';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@mantine/notifications', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    notifications: { show: vi.fn() },
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

vi.mock('../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    setPageContext: vi.fn(),
    startTour: vi.fn(),
  }),
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
}));

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

describe('Agent Workshop invalid-key recovery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('remis_tutorial_agent-workshop_prompt_seen_v1', 'true');
    sessionStorage.setItem(AGENT_WORKSHOP_STORAGE_KEY, JSON.stringify({
      active: 2,
      selectedProjectId: 'test-p',
      selectedProvider: 'gemini',
      selectedModel: 'gemini-pro',
      issues: [{
        file_name: 'events.yml',
        file_id: 'file-1',
        key: 'invalid key:0',
        error_code: 'validation_invalid_key_format',
        target_str: 'broken',
      }],
      fixedIssues: [],
      executionLogs: [],
      executing: false,
    }));
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
      if (url === '/api/project/test-p/check-archive') {
        return Promise.resolve({ data: { source_entry_count: 1 } });
      }
      if (url === '/api/project/test-p/history') {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it('explains why an invalid key cannot be edited in proofreading', async () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <AgentWorkshopPage />
        </MemoryRouter>
      </MantineProvider>,
    );

    fireEvent.click((await screen.findByText('agent_workshop.file_issue_details')).closest('button'));
    fireEvent.click((await screen.findByText('events.yml')).closest('button'));
    fireEvent.click(await screen.findByRole('button', { name: 'proofreading.open_entry' }));

    expect(notifications.show).toHaveBeenCalledWith({
      color: 'orange',
      title: 'agent_workshop.invalid_key_manual_title',
      message: 'agent_workshop.invalid_key_manual_help',
    });
  });

  it('does not offer model repair for an invalid key', async () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <AgentWorkshopPage />
        </MemoryRouter>
      </MantineProvider>,
    );

    fireEvent.click((await screen.findByText('agent_workshop.file_issue_details')).closest('button'));
    fireEvent.click((await screen.findByText('events.yml')).closest('button'));

    expect(await screen.findByRole('button', { name: 'agent_workshop.fix_btn' })).toBeDisabled();
  });
});

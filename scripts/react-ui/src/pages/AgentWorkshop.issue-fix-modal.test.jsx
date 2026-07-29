import { fireEvent, render, screen, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AgentWorkshopPage from './AgentWorkshopPage';
import { AGENT_WORKSHOP_STORAGE_KEY } from '../hooks/agentWorkshopSession';
import api from '../utils/api';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

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

describe('Agent Workshop single-repair approval modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('remis_tutorial_agent-workshop_prompt_seen_v1', 'true');
    sessionStorage.setItem(AGENT_WORKSHOP_STORAGE_KEY, JSON.stringify({
      active: 2,
      selectedProjectId: 'test-p',
      selectedProvider: 'lm_studio',
      selectedModel: 'local-model',
      issues: [{
        file_name: 'events.yml',
        file_id: 'file-1',
        key: 'valid_key',
        error_code: 'validation_format_marker_parity_mismatch',
        source_str: '#italic source#!',
        target_str: '#italic target',
        details: 'missing marker',
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
              value: 'lm_studio',
              label: 'LM Studio',
              available_models: ['local-model'],
              selected_model: 'local-model',
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

  it('shows the selected provider, model, write boundary, and paper surface', async () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <AgentWorkshopPage />
        </MemoryRouter>
      </MantineProvider>,
    );

    fireEvent.click((await screen.findByText('agent_workshop.file_issue_details')).closest('button'));
    fireEvent.click((await screen.findByText('events.yml')).closest('button'));
    fireEvent.click(await screen.findByRole('button', { name: 'agent_workshop.fix_btn' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('agent_workshop.provider_label')).toHaveValue('LM Studio');
    expect(within(dialog).getByLabelText('agent_workshop.model_label')).toHaveValue('local-model');
    expect(within(dialog).getByText('agent_workshop.single_fix_confirm_local')).toBeInTheDocument();
    expect(dialog.querySelector('[data-remis-surface="paper"]')).toBeInTheDocument();
  });
});

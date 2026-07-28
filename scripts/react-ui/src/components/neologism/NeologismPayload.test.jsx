import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import MiningDashboard from './MiningDashboard';
import JudgmentCourt from './JudgmentCourt';
import ProjectGlossaryPanel from '../project/ProjectGlossaryPanel';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, fallback) => (typeof fallback === 'string' ? fallback : key) }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

class FakeWebSocket {
  constructor() {
    this.close = vi.fn();
  }
}

const renderWithProviders = (ui) => render(
  <MemoryRouter>
    <MantineProvider>{ui}</MantineProvider>
  </MemoryRouter>,
);

describe('neologism array payload boundaries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.WebSocket = FakeWebSocket;
  });

  it('renders mining projects and files from wrapper payloads', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({ data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] } });
      }
      if (url === '/api/config') {
        return Promise.resolve({ data: { api_providers: [] } });
      }
      if (url === '/api/neologisms/mining-files/project-1') {
        return Promise.resolve({ data: { files: [{ file_path: 'events.yml', relative_path: 'events.yml' }] } });
      }
      if (url === '/api/neologisms/status/project-1') {
        return Promise.resolve({ data: { status: 'idle' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });

    renderWithProviders(
      <MiningDashboard
        selectedProject="project-1"
        onSelectedProjectChange={vi.fn()}
        onMiningComplete={vi.fn()}
      />,
    );

    expect(await screen.findByText('events.yml')).toBeInTheDocument();
  });

  it('renders tribunal projects and candidates from wrapper payloads', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({ data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] } });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({
          data: {
            candidates: [{
              id: 7,
              original: 'Hyperlane Relay',
              suggestion: '跃迁中继',
              reasoning: 'Recurring game term',
              context_snippets: [],
              duplicate_matches: [],
            }],
          },
        });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });

    renderWithProviders(
      <JudgmentCourt
        selectedProject="project-1"
        onSelectedProjectChange={vi.fn()}
      />,
    );

    expect(await screen.findAllByText('Hyperlane Relay')).not.toHaveLength(0);
    expect(screen.getByDisplayValue('跃迁中继')).toBeInTheDocument();
  });

  it('renders available glossaries from a wrapper payload', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/api/glossaries') {
        return Promise.resolve({ data: { glossaries: [{ glossary_id: 9, game_id: 'stellaris', name: 'Main Terms' }] } });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { pending_creation: true } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });

    renderWithProviders(
      <ProjectGlossaryPanel
        project={{ project_id: 'project-1', game_id: 'stellaris' }}
        t={(key) => key}
      />,
    );

    expect(await screen.findByText('project_management.project_glossary.title')).toBeInTheDocument();
    expect(screen.queryByText('project_management.project_glossary.load_failed_message')).not.toBeInTheDocument();
  });
});

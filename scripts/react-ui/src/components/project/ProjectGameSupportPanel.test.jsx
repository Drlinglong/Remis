import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import projectService from '../../services/projectService';
import ProjectGameSupportPanel from './ProjectGameSupportPanel';

vi.mock('../../services/projectService', () => ({
  default: { getGameSupport: vi.fn() },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => (options?.game ? `${key}: ${options.game}` : key),
  }),
}));

const renderPanel = (gameId = 'project_zomboid') => render(
  <MantineProvider>
    <ProjectGameSupportPanel projectId="project-42" gameId={gameId} />
  </MantineProvider>,
);

describe('ProjectGameSupportPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows recognized counts, operation limits, diagnostics, and runtime status', async () => {
    projectService.getGameSupport.mockResolvedValue({
      data: {
        game_id: 'project_zomboid',
        capabilities: {
          independent_translation_mod: true,
          paradox_deployment: false,
          source_cleanup: false,
          runtime_verified: false,
          coverage_kind: 'recognized_resources',
        },
        diagnostics: [{
          code: 'unsupported_resource',
          message: 'Unsupported map data',
          path: 'media/maps/West Point.bin',
          severity: 'warning',
        }],
        resources: [
          { path: 'media/lua/shared/Translate/EN', entry_count: 8 },
          { path: 'media/lua/client/Translate/EN', entry_count: 5 },
        ],
        metadata: { game_version: '41.78' },
      },
    });

    renderPanel();

    expect(await screen.findByRole('heading', { name: 'game_support.title' })).toBeInTheDocument();
    expect(screen.getByText('2', { selector: 'h4' })).toBeInTheDocument();
    expect(screen.getByText('13', { selector: 'h4' })).toBeInTheDocument();
    expect(screen.getByText('game_support.runtime_unverified')).toBeInTheDocument();
    expect(screen.getAllByText('game_support.unavailable')).toHaveLength(2);
    expect(screen.getByText('media/maps/West Point.bin')).toBeInTheDocument();
    expect(screen.getByText('game_support.export_guidance.independent_package')).toBeInTheDocument();
    expect(screen.getByText('game_version')).toBeInTheDocument();
    expect(projectService.getGameSupport).toHaveBeenCalledWith('project-42', expect.objectContaining({
      signal: expect.any(AbortSignal),
    }));
  });

  it('shows the CSV-only export boundary for Surviving Mars', async () => {
    projectService.getGameSupport.mockResolvedValue({
      data: {
        game_id: 'surviving_mars',
        capabilities: { independent_translation_mod: false, paradox_deployment: false, source_cleanup: false },
        diagnostics: [],
        resources: [{ path: 'translations/en.csv', entry_count: 2 }],
        metadata: {},
      },
    });

    renderPanel('surviving_mars');

    expect(await screen.findByText('game_support.export_guidance.surviving_mars_csv')).toBeInTheDocument();
    expect(screen.getByText('game_support.no_unsupported_diagnostics')).toBeInTheDocument();
  });

  it('offers a retry when the support report cannot be loaded', async () => {
    projectService.getGameSupport.mockRejectedValue(new Error('offline'));
    renderPanel('rimworld');

    fireEvent.click(await screen.findByRole('button', { name: 'game_support.retry' }));
    await waitFor(() => expect(projectService.getGameSupport).toHaveBeenCalledTimes(2));
  });

  it('does not request structured support for Paradox projects', () => {
    renderPanel('victoria3');

    expect(projectService.getGameSupport).not.toHaveBeenCalled();
    expect(screen.queryByRole('heading', { name: 'game_support.title' })).not.toBeInTheDocument();
  });
});

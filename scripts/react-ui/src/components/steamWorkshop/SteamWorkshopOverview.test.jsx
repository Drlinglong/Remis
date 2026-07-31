import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import SteamWorkshopOverview from './SteamWorkshopOverview';

vi.mock('./usePublishingWorkspaceCatalog', () => ({
  usePublishingWorkspaceCatalog: () => ({
    error: '',
    isLoading: false,
    isSaving: false,
    projectNames: new Map([['project-1', '演示项目']]),
    projects: [{ project_id: 'project-1', name: '演示项目' }],
    saveWorkspace: vi.fn(),
    workspaces: [{
      workspace_id: 'workspace-1',
      name: '演示项目发布素材',
      project_id: 'project-1',
      workshop_item_id: '3538617386',
      updated_at: '2026-07-31T10:00:00Z',
      cover_version_count: 2,
      description_version_count: 3,
      current_cover_version: { sequence: 2 },
      current_description_version: { sequence: 3 },
    }],
  }),
}));

describe('SteamWorkshopOverview', () => {
  it('summarizes binding and current versions, then enters the cover workspace', () => {
    render(
      <MantineProvider>
        <MemoryRouter initialEntries={['/steam-workshop']}>
          <Routes>
            <Route path="/steam-workshop" element={<SteamWorkshopOverview />} />
            <Route
              path="/steam-workshop/:workspaceId/:section"
              element={<div>cover workspace route</div>}
            />
          </Routes>
        </MemoryRouter>
      </MantineProvider>,
    );

    expect(screen.getByText('项目：演示项目')).toBeInTheDocument();
    expect(screen.getByText('Workshop ID: 3538617386')).toBeInTheDocument();
    expect(screen.getByText('当前采用 #2')).toBeInTheDocument();
    expect(screen.getByText('当前采用 #3')).toBeInTheDocument();
    expect(
      screen.getByText('演示项目发布素材').closest('[data-remis-surface]'),
    ).toHaveAttribute('data-remis-surface', 'paper');
    expect(screen.getByRole('button', { name: '进入工作区' }))
      .toHaveAttribute('data-remis-action', 'paper-primary');

    fireEvent.click(screen.getByRole('button', { name: '进入工作区' }));
    expect(screen.getByText('cover workspace route')).toBeInTheDocument();
  });
});

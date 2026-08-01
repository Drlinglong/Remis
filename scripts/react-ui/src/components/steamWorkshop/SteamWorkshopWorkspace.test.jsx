import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SteamWorkshopWorkspace from './SteamWorkshopWorkspace';

const workspace = {
  workspace_id: 'workspace-1',
  name: '演示发布工作区',
  project_id: 'project-1',
  workshop_item_id: '3538617386',
  current_cover_version_id: 'cover-current',
};

vi.mock('./usePublishingWorkspaceDetail', () => ({
  usePublishingWorkspaceDetail: () => ({
    error: '',
    isLoading: false,
    isSaving: false,
    projectName: '演示项目',
    projects: [],
    updateWorkspace: vi.fn(),
    workspace,
  }),
}));

vi.mock('./PublishingVersionHistory', () => ({ default: () => null }));
vi.mock('./WorkspaceEditorModal', () => ({ default: () => null }));
vi.mock('../tools/WorkshopGenerator', () => ({ default: () => null }));
vi.mock('../tools/ThumbnailGenerator', () => ({
  default: ({ editCoverVersionId }) => (
    <div data-testid="requested-cover-version">{editCoverVersionId || 'blank'}</div>
  ),
}));

const renderWorkspace = (entry) => render(
  <MantineProvider>
    <MemoryRouter initialEntries={[entry]}>
      <SteamWorkshopWorkspace activeSection="cover" workspaceId="workspace-1" />
    </MemoryRouter>
  </MantineProvider>,
);

describe('SteamWorkshopWorkspace cover edit deep links', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('forwards only the explicit cover version query to the cover editor', async () => {
    renderWorkspace('/steam-workshop/workspace-1/cover?coverVersionId=cover-v7');

    expect(await screen.findByTestId('requested-cover-version')).toHaveTextContent('cover-v7');
  });

  it('keeps ordinary cover entry unrequested', async () => {
    renderWorkspace('/steam-workshop/workspace-1/cover');

    expect(await screen.findByTestId('requested-cover-version')).toHaveTextContent('blank');
  });
});

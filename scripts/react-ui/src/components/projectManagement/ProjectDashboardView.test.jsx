import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectDashboardView } from './ProjectDashboardView';

vi.mock('../project/ProjectHistory', () => ({
  default: () => <div>history</div>,
}));

vi.mock('../project/ProjectValidation', () => ({
  default: () => <div>validation</div>,
}));

vi.mock('../project/ProjectGlossaryPanel', () => ({
  default: () => <div>project glossary</div>,
}));

vi.mock('../project/ProjectHeader', () => ({
  default: () => <div data-testid="project-workspace-status">project status and next action</div>,
}));

vi.mock('../tools/KanbanBoard', () => ({
  default: () => <div>kanban</div>,
}));

vi.mock('../tools/ProjectOverview', () => ({
  default: () => <div>overview</div>,
}));

vi.mock('../steamWorkshop/SteamWorkshopOverview', () => ({
  default: ({ projectId }) => <div>publishing assets for {projectId}</div>,
}));

const renderDashboard = (props = {}) => {
  const defaultProps = {
    activeTab: 'overview',
    fetchProjectFiles: vi.fn(),
    fetchProjects: vi.fn(),
    handleFileStatusChange: vi.fn(),
    handleOpenManage: vi.fn(),
    handleProofread: vi.fn(),
    handleRefreshFiles: vi.fn(),
    handleRepairMetadata: vi.fn(),
    handleUpdateNotes: vi.fn(),
    handleUpdateStatus: vi.fn(),
    metadataRepairLoading: false,
    projectDataRefreshToken: 0,
    projectDetails: { project_id: 'proj-1', files: [], overview: {} },
    selectedProject: {
      project_id: 'proj-1',
      name: 'Demo Project',
      status: 'active',
      game_id: 'vic3',
    },
    setActiveTab: vi.fn(),
    setDeleteModalOpen: vi.fn(),
    setProjectDataRefreshToken: vi.fn(),
    setSelectedProjectId: vi.fn(),
    t: (key) => key,
  };

  return render(
    <MantineProvider>
      <ProjectDashboardView {...defaultProps} {...props} />
    </MantineProvider>
  );
};

describe('ProjectDashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reloads project files when returning from Kanban to the overview tab', async () => {
    const fetchProjectFiles = vi.fn();
    const handleRefreshFiles = vi.fn();

    const { rerender } = renderDashboard({
      activeTab: 'taskboard',
      fetchProjectFiles,
      handleRefreshFiles,
    });

    expect(fetchProjectFiles).not.toHaveBeenCalled();

    rerender(
      <MantineProvider>
        <ProjectDashboardView
          activeTab="overview"
          fetchProjectFiles={fetchProjectFiles}
          fetchProjects={vi.fn()}
          handleFileStatusChange={vi.fn()}
          handleOpenManage={vi.fn()}
          handleProofread={vi.fn()}
          handleRefreshFiles={handleRefreshFiles}
          handleRepairMetadata={vi.fn()}
          handleUpdateNotes={vi.fn()}
          handleUpdateStatus={vi.fn()}
          metadataRepairLoading={false}
          projectDataRefreshToken={0}
          projectDetails={{ project_id: 'proj-1', files: [], overview: {} }}
          selectedProject={{
            project_id: 'proj-1',
            name: 'Demo Project',
            status: 'active',
            game_id: 'vic3',
          }}
          setActiveTab={vi.fn()}
          setDeleteModalOpen={vi.fn()}
          setProjectDataRefreshToken={vi.fn()}
          setSelectedProjectId={vi.fn()}
          t={(key) => key}
        />
      </MantineProvider>
    );

    await waitFor(() => {
      expect(fetchProjectFiles).toHaveBeenCalledWith('proj-1');
    });
    expect(handleRefreshFiles).not.toHaveBeenCalled();
  });

  it('keeps project-scoped publishing assets in the stable tool navigation', () => {
    const setActiveTab = vi.fn();
    renderDashboard({ setActiveTab });

    fireEvent.click(screen.getByRole('tab', {
      name: 'project_management.tabs_publishing_assets',
    }));

    expect(setActiveTab).toHaveBeenCalledWith('publishing_assets');
  });

  it('keeps project identity and the next-action summary above the tabs', () => {
    renderDashboard();

    const header = screen.getByRole('banner');
    expect(header).toHaveTextContent('Demo Project');
    expect(screen.getByTestId('project-workspace-status')).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'project_management.workspace_navigation' })).toBeInTheDocument();
  });

  it('passes the selected project into the publishing assets panel', () => {
    renderDashboard({ activeTab: 'publishing_assets' });

    expect(screen.getByText('publishing assets for proj-1')).toBeInTheDocument();
  });
});

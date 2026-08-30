import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectHeader from './ProjectHeader';

const navigateMock = vi.fn();

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, fallback) => fallback || key,
  }),
}));

const renderWithProvider = (ui) =>
  render(<MantineProvider>{ui}</MantineProvider>);

const baseProjectDetails = {
  project_id: 'proj-42',
  status: 'active',
  overview: {
    totalFiles: 12,
    totalLines: 340,
    translated: 65,
    toBeProofread: 0,
  },
};

describe('ProjectHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows active project actions and navigates to translation', async () => {
    const handleStatusChange = vi.fn();
    const onDeleteForever = vi.fn();
    const onManageProject = vi.fn();

    renderWithProvider(
      <ProjectHeader
        projectDetails={baseProjectDetails}
        handleStatusChange={handleStatusChange}
        onDeleteForever={onDeleteForever}
        onManageProject={onManageProject}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'project_management.project_menu' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'project_management.archive_project' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.primary_continue_translation' }));

    expect(handleStatusChange).toHaveBeenCalledWith('archived');
    expect(onManageProject).not.toHaveBeenCalled();
    expect(navigateMock).toHaveBeenCalledWith('/translation?projectId=proj-42');
    expect(screen.getByLabelText('Project progress')).toBeInTheDocument();
    expect(screen.getByText('Scan')).toBeInTheDocument();
    expect(screen.getByText('Validation')).toBeInTheDocument();
  });

  it('shows archived project actions for restore and soft delete', async () => {
    const handleStatusChange = vi.fn();

    renderWithProvider(
      <ProjectHeader
        projectDetails={{ ...baseProjectDetails, status: 'archived' }}
        handleStatusChange={handleStatusChange}
        onDeleteForever={vi.fn()}
        onManageProject={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'project_management.restore_project' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.project_menu' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'project_management.delete_project' }));

    expect(handleStatusChange).toHaveBeenNthCalledWith(1, 'active');
    expect(handleStatusChange).toHaveBeenNthCalledWith(2, 'deleted');
  });

  it('offers direct deployment when at least one translated version is available', () => {
    renderWithProvider(
      <ProjectHeader
        projectDetails={{
          ...baseProjectDetails,
          has_available_translation: true,
          overview: { ...baseProjectDetails.overview, toBeProofread: 35 },
          validation: { issues_count: 0 },
        }}
        handleStatusChange={vi.fn()}
        onDeleteForever={vi.fn()}
        onManageProject={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', {
      name: 'project_management.translation_available_title',
    })).toBeInTheDocument();
    expect(screen.getByText('project_management.translation_available_hint')).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'project_management.primary_continue_proofreading',
    })).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'project_management.direct_deploy',
    })).toBeInTheDocument();
  });

  it('shows deleted project actions for restore and permanent delete', async () => {
    const handleStatusChange = vi.fn();
    const onDeleteForever = vi.fn();

    renderWithProvider(
      <ProjectHeader
        projectDetails={{ ...baseProjectDetails, status: 'deleted' }}
        handleStatusChange={handleStatusChange}
        onDeleteForever={onDeleteForever}
        onManageProject={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'project_management.restore_project' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.project_menu' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'project_management.delete_forever' }));

    expect(handleStatusChange).toHaveBeenCalledWith('active');
    expect(onDeleteForever).toHaveBeenCalledOnce();
  });
});

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectHeader from './ProjectHeader';

const navigateMock = vi.fn();

vi.mock('react-router-dom', () => ({
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
    toBeProofread: 20,
  },
};

describe('ProjectHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows active project actions and navigates to translation', () => {
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

    fireEvent.click(screen.getByRole('button', { name: 'project_management.archive_project' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_project' }));
    fireEvent.click(screen.getByRole('button', { name: '开始翻译' }));

    expect(handleStatusChange).toHaveBeenCalledWith('archived');
    expect(onManageProject).toHaveBeenCalledOnce();
    expect(navigateMock).toHaveBeenCalledWith('/translation?projectId=proj-42');
  });

  it('shows archived project actions for restore and soft delete', () => {
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
    fireEvent.click(screen.getByRole('button', { name: 'project_management.delete_project' }));

    expect(handleStatusChange).toHaveBeenNthCalledWith(1, 'active');
    expect(handleStatusChange).toHaveBeenNthCalledWith(2, 'deleted');
  });

  it('shows deleted project actions for restore and permanent delete', () => {
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
    fireEvent.click(screen.getByRole('button', { name: 'project_management.delete_forever' }));

    expect(handleStatusChange).toHaveBeenCalledWith('active');
    expect(onDeleteForever).toHaveBeenCalledOnce();
  });
});

import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CreateProjectModal } from './CreateProjectModal';
import service from '../../services/marsPipelineService';

vi.mock('../../services/marsPipelineService', () => ({ default: {
  inspectInput: vi.fn(), planImport: vi.fn(), import: vi.fn(),
} }));
vi.mock('../project/MarsPipelineImport', () => ({ default: () => null }));

const props = () => ({ opened: true, availableGames: [{ value: 'surviving_mars', label: 'Surviving Mars' }],
  availableLanguages: [{ value: 'en', label: 'English' }], newProjectName: 'Grom',
  newProjectGame: 'surviving_mars', newProjectPath: 'J:/workshop/3816401225',
  newProjectSourceLang: 'en', newProjectImportMode: 'copy', isCreatingProject: false,
  createProgressMessage: '', setNewProjectName: vi.fn(), setNewProjectGame: vi.fn(),
  setNewProjectPath: vi.fn(), setNewProjectSourceLang: vi.fn(), setNewProjectImportMode: vi.fn(),
  handleBrowseFolder: vi.fn(), handleCreateProject: vi.fn(), onPipelineCreated: vi.fn(), onClose: vi.fn(),
  t: (key, fallback) => fallback || ({ form_label_project_name: 'Project name',
    form_label_folder_path: 'Folder path', form_label_source_language: 'Source language',
    'project_management.actions.create_new': 'Create project' }[key] || key),
});

describe('Unified Mars project form', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    service.inspectInput.mockResolvedValue({ data: { kind: 'archive', archive_path: 'J:/mod/ModContent.fpk' } });
    service.planImport.mockResolvedValue({ data: { plan_id: 'plan', source_blockers: [],
      review_items: [{ id: 'needs-review' }], allowed_actions: ['approve_preparation'] } });
    service.import.mockResolvedValue({ data: { status: 'prepared', project_id: 'project' } });
  });

  it('creates a project from the one-window form without showing CSV internals', async () => {
    const options = props();
    render(<MantineProvider><CreateProjectModal {...options} /></MantineProvider>);
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
    expect(screen.getByLabelText('Project name')).toHaveValue('Grom');
    expect(screen.getByLabelText('Folder path')).toHaveValue(options.newProjectPath);
    expect(screen.getByLabelText('Source language', { selector: 'input' })).toHaveValue('English');
    expect(screen.queryByLabelText('Source CSV table (optional)')).not.toBeInTheDocument();
    expect(service.inspectInput).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }));
    await waitFor(() => expect(options.onPipelineCreated).toHaveBeenCalledWith('project'));
    expect(options.handleCreateProject).not.toHaveBeenCalled();
  });

  it('keeps validation errors in the same form without creating a project', async () => {
    service.inspectInput.mockRejectedValue({ response: { data: { detail: { message: 'Multiple archives: choose a file' } } } });
    const options = props();
    render(<MantineProvider><CreateProjectModal {...options} /></MantineProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }));
    expect(await screen.findByText('Multiple archives: choose a file')).toBeInTheDocument();
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
    expect(options.onPipelineCreated).not.toHaveBeenCalled();
    expect(service.import).not.toHaveBeenCalled();
  });

  it('imports editable folders through the normal project path without another form', async () => {
    service.inspectInput.mockResolvedValue({ data: { kind: 'editable_folder' } });
    const options = props();
    render(<MantineProvider><CreateProjectModal {...options} /></MantineProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }));
    await waitFor(() => expect(options.handleCreateProject).toHaveBeenCalledOnce());
    expect(service.planImport).not.toHaveBeenCalled();
  });
});

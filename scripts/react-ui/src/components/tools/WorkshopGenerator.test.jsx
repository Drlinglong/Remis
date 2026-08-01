import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkshopGenerator from './WorkshopGenerator';
import { useDescriptionWorkspace } from '../steamWorkshop/description/useDescriptionWorkspace';

vi.mock('../steamWorkshop/description/useDescriptionWorkspace', () => ({
  useDescriptionWorkspace: vi.fn(),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

const saveCandidate = vi.fn();
const adoptVersion = vi.fn();
const setEditor = vi.fn();
const generateCandidate = vi.fn();

const hookState = {
  adoptVersion,
  chooseVersion: vi.fn(),
  createWorkspace: vi.fn(),
  editor: {
    bbcode: '[b]可编辑内容[/b]',
    language: 'zh',
    parentVersionId: null,
  },
  error: '',
  generateCandidate,
  isGenerating: false,
  isLoading: false,
  isSaving: false,
  saveCandidate,
  selectWorkspace: vi.fn(),
  setEditor,
  versions: [],
  workspace: {
    workspace_id: 'workspace-1',
    name: '测试工作区',
    project_id: 'project-1',
    workshop_item_id: null,
    current_description_version_id: null,
  },
  workspaces: [{ workspace_id: 'workspace-1', name: '测试工作区' }],
};

describe('WorkshopGenerator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDescriptionWorkspace.mockReturnValue(hookState);
  });

  it('passes an explicit project context and treats Workshop ID as optional', () => {
    render(
      <MantineProvider>
        <WorkshopGenerator projectId="project-1" projectName="测试项目" />
      </MantineProvider>,
    );

    expect(useDescriptionWorkspace).toHaveBeenCalledWith({
      projectId: 'project-1',
      requestedWorkspaceId: null,
    });
    expect(screen.getByText('尚未绑定 Workshop ID')).toBeInTheDocument();
  });

  it('saves a candidate without adopting it', async () => {
    saveCandidate.mockResolvedValue({
      version_id: 'version-1',
      sequence: 1,
    });
    render(
      <MantineProvider>
        <WorkshopGenerator projectId="project-1" />
      </MantineProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: '保存候选版本' }));

    await waitFor(() => expect(saveCandidate).toHaveBeenCalledTimes(1));
    expect(adoptVersion).not.toHaveBeenCalled();
  });

  it('keeps model generation unavailable until a Workshop ID is bound', () => {
    render(
      <MantineProvider>
        <WorkshopGenerator />
      </MantineProvider>,
    );

    expect(screen.getByRole('button', { name: '模型生成' })).toBeDisabled();
    expect(generateCandidate).not.toHaveBeenCalled();
  });
});

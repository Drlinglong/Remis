import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDescriptionWorkspace } from './useDescriptionWorkspace';
import * as service from './descriptionService';

vi.mock('./descriptionService', () => ({
  createDescriptionVersion: vi.fn(),
  createPublishingWorkspace: vi.fn(),
  getPublishingWorkspace: vi.fn(),
  listDescriptionVersions: vi.fn(),
  listPublishingWorkspaces: vi.fn(),
  selectDescriptionVersion: vi.fn(),
}));

const workspace = {
  workspace_id: 'workspace-1',
  name: '项目发布素材',
  project_id: 'project-1',
  workshop_item_id: null,
  current_description_version_id: null,
};

describe('useDescriptionWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    service.listPublishingWorkspaces.mockResolvedValue([workspace]);
    service.getPublishingWorkspace.mockResolvedValue(workspace);
    service.listDescriptionVersions.mockResolvedValue([]);
  });

  it('loads only the supplied project context', async () => {
    const { result } = renderHook(() => useDescriptionWorkspace({
      projectId: 'project-1',
      requestedWorkspaceId: null,
    }));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(service.listPublishingWorkspaces).toHaveBeenCalledWith({ projectId: 'project-1' });
    expect(result.current.workspace).toEqual(workspace);
  });

  it('saves a candidate without selecting it automatically', async () => {
    const candidate = {
      version_id: 'version-1',
      sequence: 1,
      bbcode: '[b]候选[/b]',
      language: 'zh',
      source: 'manual',
    };
    service.createDescriptionVersion.mockResolvedValue(candidate);
    const { result } = renderHook(() => useDescriptionWorkspace({
      projectId: 'project-1',
      requestedWorkspaceId: null,
    }));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.setEditor({
        bbcode: '[b]候选[/b]',
        language: 'zh',
        parentVersionId: null,
      });
    });
    await act(async () => {
      await result.current.saveCandidate();
    });

    expect(service.createDescriptionVersion).toHaveBeenCalledWith('workspace-1', {
      bbcode: '[b]候选[/b]',
      language: 'zh',
      source: 'manual',
      parent_version_id: null,
      metadata: {},
    });
    expect(service.selectDescriptionVersion).not.toHaveBeenCalled();
    expect(result.current.versions[0]).toEqual(candidate);
  });

  it('refreshes workspace and history after explicit adoption', async () => {
    const selectedWorkspace = {
      ...workspace,
      current_description_version_id: 'version-1',
    };
    service.selectDescriptionVersion.mockResolvedValue({ version_id: 'version-1' });
    service.getPublishingWorkspace
      .mockResolvedValueOnce(workspace)
      .mockResolvedValueOnce(selectedWorkspace);
    const { result } = renderHook(() => useDescriptionWorkspace({
      projectId: 'project-1',
      requestedWorkspaceId: null,
    }));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.adoptVersion('version-1');
    });

    expect(service.selectDescriptionVersion).toHaveBeenCalledWith('workspace-1', 'version-1');
    expect(result.current.workspace.current_description_version_id).toBe('version-1');
  });
});

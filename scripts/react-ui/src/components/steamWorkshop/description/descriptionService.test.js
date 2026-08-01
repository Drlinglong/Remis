import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../../../utils/api';
import {
  createDescriptionVersion,
  createPublishingWorkspace,
  listDescriptionVersions,
  listPublishingWorkspaces,
  selectDescriptionVersion,
  updatePublishingWorkspace,
} from './descriptionService';

vi.mock('../../../utils/api', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));

describe('descriptionService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps project and Workshop ID optional when creating a workspace', async () => {
    api.post.mockResolvedValue({ data: { workspace_id: 'workspace-1' } });

    await createPublishingWorkspace({
      name: '未绑定工作区',
      game_id: null,
      project_id: null,
      workshop_item_id: null,
    });

    expect(api.post).toHaveBeenCalledWith('/api/steam-workshop/workspaces', {
      name: '未绑定工作区',
      game_id: null,
      project_id: null,
      workshop_item_id: null,
    });
  });

  it('filters a project workspace without reading project.workshop_id', async () => {
    api.get.mockResolvedValue({ data: [] });

    await listPublishingWorkspaces({ projectId: 'project-1' });

    expect(api.get).toHaveBeenCalledWith('/api/steam-workshop/workspaces', {
      params: { project_id: 'project-1' },
    });
  });

  it('allows a workspace to bind or replace its optional Workshop ID later', async () => {
    api.patch.mockResolvedValue({
      data: { workspace_id: 'workspace-1', workshop_item_id: '3538617386' },
    });

    await updatePublishingWorkspace('workspace-1', {
      workshop_item_id: '3538617386',
    });

    expect(api.patch).toHaveBeenCalledWith(
      '/api/steam-workshop/workspaces/workspace-1',
      { workshop_item_id: '3538617386' },
    );
  });

  it('persists and selects description versions through separate actions', async () => {
    api.post.mockResolvedValue({ data: {} });

    await createDescriptionVersion('workspace-1', {
      bbcode: '[b]候选[/b]',
      language: 'zh',
      source: 'manual',
      parent_version_id: null,
      metadata: {},
    });
    await selectDescriptionVersion('workspace-1', 'version-1');

    expect(api.post).toHaveBeenNthCalledWith(
      1,
      '/api/steam-workshop/workspaces/workspace-1/versions/description',
      expect.objectContaining({ bbcode: '[b]候选[/b]', source: 'manual' }),
    );
    expect(api.post).toHaveBeenNthCalledWith(
      2,
      '/api/steam-workshop/workspaces/workspace-1/selections/description',
      { version_id: 'version-1' },
    );
  });

  it('requests description history explicitly', async () => {
    api.get.mockResolvedValue({ data: [] });

    await listDescriptionVersions('workspace-1');

    expect(api.get).toHaveBeenCalledWith(
      '/api/steam-workshop/workspaces/workspace-1/versions',
      { params: { asset_type: 'description' } },
    );
  });
});

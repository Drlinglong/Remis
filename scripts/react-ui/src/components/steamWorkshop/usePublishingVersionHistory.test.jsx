import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import steamWorkshopCoverService from '../../services/steamWorkshopCoverService';
import {
  getPublishingWorkspace,
  listPublishingVersions,
} from './description/descriptionService';
import { usePublishingVersionHistory } from './usePublishingVersionHistory';

vi.mock('../../services/steamWorkshopCoverService', () => ({
  default: {
    resolveMediaUrl: vi.fn((path) => `http://127.0.0.1:1453${path}`),
    selectVersion: vi.fn(),
  },
}));

vi.mock('./description/descriptionService', () => ({
  getPublishingWorkspace: vi.fn(),
  deletePublishingVersion: vi.fn(),
  listPublishingVersions: vi.fn(),
  selectDescriptionVersion: vi.fn(),
}));

describe('usePublishingVersionHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPublishingWorkspace.mockResolvedValue({ workspace_id: 'workspace-1' });
    listPublishingVersions.mockResolvedValue([
      {
        version_id: 'cover-v1',
        asset_type: 'cover',
        content_url: '/api/steam-workshop/versions/cover-v1/content',
      },
    ]);
  });

  it('normalizes cover preview URLs through the configured backend origin', async () => {
    const { result } = renderHook(() => usePublishingVersionHistory('workspace-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(steamWorkshopCoverService.resolveMediaUrl).toHaveBeenCalledWith(
      '/api/steam-workshop/versions/cover-v1/content',
    );
    expect(result.current.versions[0].content_url).toBe(
      'http://127.0.0.1:1453/api/steam-workshop/versions/cover-v1/content',
    );
  });
});

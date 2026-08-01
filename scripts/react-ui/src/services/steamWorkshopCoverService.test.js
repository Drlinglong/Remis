import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../utils/api';
import steamWorkshopCoverService from './steamWorkshopCoverService';

vi.mock('../utils/api', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

describe('steamWorkshopCoverService', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('saves the canvas and real PNG bytes in one immutable version request', async () => {
        api.post.mockResolvedValue({ data: { version_id: 'cover-v2' } });
        const canvas = { schema_version: 1, elements: [] };

        await steamWorkshopCoverService.createVersion('workspace-1', {
            pngDataUrl: 'data:image/png;base64,cG5nLWJ5dGVz',
            canvas,
            parentVersionId: 'cover-v1',
        });

        expect(api.post).toHaveBeenCalledWith(
            '/api/steam-workshop/workspaces/workspace-1/versions/cover',
            {
                png_base64: 'cG5nLWJ5dGVz',
                canvas,
                source: 'manual',
                parent_version_id: 'cover-v1',
                metadata: {
                    editor: 'remis-cover-editor',
                    canvas_schema_version: 1,
                },
            },
        );
    });

    it('uses the typed cover filter and selection endpoint', async () => {
        api.get.mockResolvedValue({ data: [] });
        api.post.mockResolvedValue({ data: {} });

        await steamWorkshopCoverService.listVersions('workspace-1');
        await steamWorkshopCoverService.selectVersion('workspace-1', 'cover-v3');

        expect(api.get).toHaveBeenCalledWith(
            '/api/steam-workshop/workspaces/workspace-1/versions',
            { params: { asset_type: 'cover' } },
        );
        expect(api.post).toHaveBeenCalledWith(
            '/api/steam-workshop/workspaces/workspace-1/selections/cover',
            { version_id: 'cover-v3' },
        );
    });

    it('keeps the project-thumbnail request scoped to its workspace', () => {
        expect(steamWorkshopCoverService.getProjectThumbnailUrl('workspace-1')).toBe(
            '/api/steam-workshop/workspaces/workspace-1/project-thumbnail',
        );
    });
});

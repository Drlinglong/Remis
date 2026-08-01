import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import steamWorkshopCoverService from '../../../services/steamWorkshopCoverService';
import { useCoverVersions } from './useCoverVersions';

vi.mock('../../../services/steamWorkshopCoverService', () => ({
    default: {
        listVersions: vi.fn(),
        getVersion: vi.fn(),
        createVersion: vi.fn(),
        selectVersion: vi.fn(),
    },
}));

describe('useCoverVersions', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        steamWorkshopCoverService.listVersions.mockResolvedValue({
            versions: [{ version_id: 'cover-v1', sequence: 1 }],
        });
    });

    it('loads only the active workspace history and preserves parent lineage when saving', async () => {
        steamWorkshopCoverService.createVersion.mockResolvedValue({ version_id: 'cover-v2' });
        const { result } = renderHook(() => useCoverVersions({
            workspaceId: 'workspace-1',
            currentVersionId: 'cover-v1',
            onLoadCanvas: vi.fn(),
        }));
        await waitFor(() => expect(result.current.versions).toHaveLength(1));

        await act(async () => {
            await result.current.saveVersion({
                pngDataUrl: 'data:image/png;base64,cG5n',
                canvas: { schema_version: 1 },
            });
        });

        expect(steamWorkshopCoverService.createVersion).toHaveBeenCalledWith('workspace-1', {
            pngDataUrl: 'data:image/png;base64,cG5n',
            canvas: { schema_version: 1 },
            parentVersionId: 'cover-v1',
        });
        expect(steamWorkshopCoverService.listVersions).toHaveBeenCalledTimes(2);
    });

    it('loads canvas data for editing without implicitly selecting the version', async () => {
        const onLoadCanvas = vi.fn();
        steamWorkshopCoverService.getVersion.mockResolvedValue({
            version_id: 'cover-v2',
            canvas: { schema_version: 1, elements: [] },
        });
        const { result } = renderHook(() => useCoverVersions({
            workspaceId: 'workspace-1',
            currentVersionId: 'cover-v1',
            onLoadCanvas,
        }));
        await waitFor(() => expect(result.current.versions).toHaveLength(1));

        await act(async () => {
            await result.current.loadVersion('cover-v2');
        });

        expect(onLoadCanvas).toHaveBeenCalledWith({ schema_version: 1, elements: [] });
        expect(steamWorkshopCoverService.selectVersion).not.toHaveBeenCalled();
    });

    it('selects a version only through the explicit selection action', async () => {
        steamWorkshopCoverService.selectVersion.mockResolvedValue({});
        const { result } = renderHook(() => useCoverVersions({
            workspaceId: 'workspace-1',
            onLoadCanvas: vi.fn(),
        }));
        await waitFor(() => expect(result.current.versions).toHaveLength(1));

        await act(async () => {
            await result.current.selectVersion('cover-v1');
        });

        expect(steamWorkshopCoverService.selectVersion).toHaveBeenCalledWith('workspace-1', 'cover-v1');
        expect(result.current.selectedVersionId).toBe('cover-v1');
    });
});

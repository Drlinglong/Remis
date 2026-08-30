import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useContextArchiveTree } from './useContextArchiveTree';
import { treeFixture } from './contextArchiveTreeFixture';

describe('useContextArchiveTree', () => {
    it('keeps relationship edits local until an adapter is supplied', () => {
        const { result } = renderHook(() => useContextArchiveTree({ initialTree: treeFixture }));

        act(() => result.current.moveFragment({
            fragmentId: 'fragment-2',
            targetGroupId: 'group-choice',
        }));

        expect(result.current.dirty).toBe(true);
        expect(result.current.canSave).toBe(false);
        expect(result.current.tree.groups[1].fragmentIds).toEqual(['fragment-2']);
    });

    it('loads and saves through the API adapter seam', async () => {
        const adapter = {
            load: vi.fn().mockResolvedValue({ tree: treeFixture }),
            save: vi.fn().mockResolvedValue({ tree: treeFixture }),
        };
        const { result } = renderHook(() => useContextArchiveTree({
            initialTree: null,
            adapter,
            enabled: true,
            projectId: 'project-1',
            releaseId: 'release-1',
        }));

        await waitFor(() => {
            expect(adapter.load).toHaveBeenCalledTimes(1);
            expect(result.current.tree.available).toBe(true);
        });
        act(() => result.current.renameStory('story-main', 'Renamed story'));
        await act(async () => {
            await result.current.save();
        });

        expect(adapter.save).toHaveBeenCalledWith(expect.objectContaining({
            projectId: 'project-1',
            releaseId: 'release-1',
            tree: expect.objectContaining({ stories: expect.any(Array) }),
        }));
        expect(result.current.dirty).toBe(false);
    });
});

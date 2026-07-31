import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
    createEmptyCoverCanvas,
    readCoverDraft,
    writeCoverDraft,
} from './coverCanvasState';
import { useCoverDraft } from './useCoverDraft';

const memoryStorage = () => {
    const values = new Map();
    return {
        getItem: (key) => values.get(key) ?? null,
        setItem: vi.fn((key, value) => values.set(key, value)),
    };
};

describe('useCoverDraft', () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it('starts with a blank canvas instead of restoring the persisted draft', async () => {
        const storage = memoryStorage();
        const canvas = {
            schema_version: 1,
            width: 512,
            height: 512,
            backgroundColor: '#ffffff',
            backgroundImage: null,
            elements: [],
        };
        writeCoverDraft(storage, { projectId: 'project-1' }, canvas);
        const replaceCanvas = vi.fn();

        const { result } = renderHook(() => useCoverDraft({
            projectId: 'project-1',
            workspaceId: null,
            canvasState: {
                backgroundColor: '#ffffff',
                backgroundImage: null,
                elements: [],
            },
            replaceCanvas,
            storage,
        }));

        await waitFor(() => expect(result.current.restored).toBe(true));
        expect(replaceCanvas).not.toHaveBeenCalled();
    });

    it('clears the editor and persisted draft immediately without a stale autosave', async () => {
        vi.useFakeTimers();
        const storage = memoryStorage();
        const context = { projectId: 'project-1', workspaceId: null };
        writeCoverDraft(storage, context, {
            schema_version: 1,
            width: 512,
            height: 512,
            backgroundColor: '#222222',
            backgroundImage: null,
            elements: [{ id: 'persisted-text', type: 'text', text: 'persisted' }],
        });
        const replaceCanvas = vi.fn();
        const { result } = renderHook(() => useCoverDraft({
            ...context,
            canvasState: {
                backgroundColor: '#222222',
                backgroundImage: { src: 'data:image/png;base64,background' },
                elements: [{ id: 'text-1', type: 'text', text: 'stale' }],
            },
            replaceCanvas,
            storage,
        }));

        await act(async () => {
            result.current.clearCanvas();
        });

        expect(replaceCanvas).toHaveBeenCalledWith(createEmptyCoverCanvas());
        expect(readCoverDraft(storage, context)).toEqual(createEmptyCoverCanvas());

        await act(async () => {
            await vi.advanceTimersByTimeAsync(601);
        });

        expect(readCoverDraft(storage, context)).toEqual(createEmptyCoverCanvas());
    });

    it('debounces autosave instead of creating a version per canvas change', async () => {
        vi.useFakeTimers();
        const storage = memoryStorage();
        const canvasState = {
            backgroundColor: '#222222',
            backgroundImage: null,
            elements: [],
        };
        const { result } = renderHook(() => useCoverDraft({
            projectId: null,
            workspaceId: 'workspace-1',
            canvasState,
            replaceCanvas: vi.fn(),
            storage,
        }));
        await act(async () => {});

        await act(async () => {
            await vi.advanceTimersByTimeAsync(601);
        });

        expect(storage.setItem).toHaveBeenCalledTimes(1);
        expect(result.current.draftSavedAt).toBeInstanceOf(Date);
    });
});

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { writeCoverDraft } from './coverCanvasState';
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

    it('restores the draft for the active project context', async () => {
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
        expect(replaceCanvas).toHaveBeenCalledWith({
            backgroundColor: '#ffffff',
            backgroundImage: null,
            elements: [],
        });
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

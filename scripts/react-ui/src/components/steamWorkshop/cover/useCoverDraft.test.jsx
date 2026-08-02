import React from 'react';
import { act, renderHook } from '@testing-library/react';
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

    it('restores the persisted draft before autosave can replace it', async () => {
        vi.useFakeTimers();
        const storage = memoryStorage();
        const canvas = {
            schema_version: 1,
            width: 512,
            height: 512,
            backgroundColor: '#222222',
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
        }), { wrapper: React.StrictMode });

        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(result.current.restored).toBe(true);
        expect(replaceCanvas).toHaveBeenCalledWith({
            backgroundColor: '#222222',
            backgroundImage: null,
            elements: [],
        });
        await act(async () => {
            await vi.advanceTimersByTimeAsync(601);
        });
        expect(readCoverDraft(storage, { projectId: 'project-1' })).toEqual(canvas);
    });

    it('recovers autosave after a persisted image cannot be hydrated', async () => {
        vi.useFakeTimers();
        const OriginalImage = window.Image;
        window.Image = class BrokenImage {
            set src(_value) {
                this.onerror?.();
            }
        };
        const storage = memoryStorage();
        const context = { projectId: 'project-1', workspaceId: null };
        writeCoverDraft(storage, context, {
            ...createEmptyCoverCanvas(),
            backgroundImage: { src: 'missing://cover.png' },
        });
        const replaceCanvas = vi.fn();
        const { result, rerender } = renderHook(({ canvasState }) => useCoverDraft({
            ...context,
            canvasState,
            replaceCanvas,
            storage,
        }), {
            initialProps: {
                canvasState: {
                    backgroundColor: '#ffffff',
                    backgroundImage: null,
                    elements: [],
                },
            },
        });

        try {
            await act(async () => {
                await Promise.resolve();
                await Promise.resolve();
            });

            expect(result.current.restored).toBe(true);
            expect(result.current.draftError).toMatchObject({
                message: 'cover_image_restore_failed',
            });
            expect(replaceCanvas).toHaveBeenCalledWith(createEmptyCoverCanvas());

            rerender({ canvasState: createEmptyCoverCanvas() });
            rerender({
                canvasState: {
                    backgroundColor: '#222222',
                    backgroundImage: null,
                    elements: [],
                },
            });
            await act(async () => {
                await vi.advanceTimersByTimeAsync(601);
            });

            expect(readCoverDraft(storage, context)).toEqual({
                ...createEmptyCoverCanvas(),
                backgroundColor: '#222222',
            });
            expect(result.current.draftError).toBe(null);
        } finally {
            window.Image = OriginalImage;
        }
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
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(result.current.restored).toBe(true);

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
        const initialCanvasState = {
            backgroundColor: '#ffffff',
            backgroundImage: null,
            elements: [],
        };
        const { result, rerender } = renderHook(({ canvasState }) => useCoverDraft({
            projectId: null,
            workspaceId: 'workspace-1',
            canvasState,
            replaceCanvas: vi.fn(),
            storage,
        }), { initialProps: { canvasState: initialCanvasState } });
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(result.current.restored).toBe(true);

        rerender({
            canvasState: {
                backgroundColor: '#222222',
                backgroundImage: null,
                elements: [],
            },
        });

        await act(async () => {
            await vi.advanceTimersByTimeAsync(601);
        });

        expect(storage.setItem).toHaveBeenCalledTimes(1);
        expect(result.current.draftSavedAt).toBeInstanceOf(Date);
    });
});

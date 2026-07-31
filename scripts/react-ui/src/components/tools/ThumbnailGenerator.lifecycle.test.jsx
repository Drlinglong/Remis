import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
    const state = {
        clearDraftCanvas: null,
        draftState: null,
        editor: null,
        loadCanvas: null,
        loadVersion: null,
    };

    return {
        hydrateCoverCanvas: vi.fn(),
        serializeCoverCanvas: vi.fn((canvas) => canvas),
        state,
        useCoverDraft: vi.fn(() => state.draftState),
        useCoverEditor: vi.fn(() => state.editor),
        useCoverVersions: vi.fn(({ onLoadCanvas }) => {
            state.loadCanvas = onLoadCanvas;
            return {
                busyAction: null,
                error: null,
                loadVersion: state.loadVersion,
                saveVersion: vi.fn(),
            };
        }),
    };
});

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key, options) => options?.defaultValue || key,
    }),
}));

vi.mock('html2canvas', () => ({ default: vi.fn() }));

vi.mock('../steamWorkshop/cover/coverCanvasState', () => ({
    hydrateCoverCanvas: mocks.hydrateCoverCanvas,
    serializeCoverCanvas: mocks.serializeCoverCanvas,
}));

vi.mock('../steamWorkshop/cover/useCoverDraft', () => ({
    useCoverDraft: mocks.useCoverDraft,
}));

vi.mock('../steamWorkshop/cover/useCoverEditor', () => ({
    useCoverEditor: mocks.useCoverEditor,
}));

vi.mock('../steamWorkshop/cover/useCoverVersions', () => ({
    useCoverVersions: mocks.useCoverVersions,
}));

vi.mock('../steamWorkshop/cover/CoverCanvas', () => ({ CoverCanvas: () => null }));
vi.mock('../steamWorkshop/cover/CoverInspector', () => ({ CoverInspector: () => null }));
vi.mock('../steamWorkshop/cover/CoverVersionPanel', () => ({ CoverVersionPanel: () => null }));
vi.mock('../steamWorkshop/cover/CoverToolbox', async () => {
    const { createElement } = await vi.importActual('react');
    return {
        CoverToolbox: ({ editor }) => createElement(
            'button',
            { type: 'button', onClick: editor.clearCanvas },
            'delete canvas',
        ),
    };
});

import ThumbnailGenerator from './ThumbnailGenerator';

const createEditor = (replaceCanvas) => ({
    addFileImage: vi.fn(),
    backgroundColor: '#ffffff',
    backgroundImage: null,
    canvasState: {
        backgroundColor: '#ffffff',
        backgroundImage: null,
        elements: [],
    },
    elements: [],
    inputRefs: {
        backgroundInputRef: { current: null },
    },
    replaceCanvas,
    selectedId: null,
    setSelectedId: vi.fn(),
});

const renderGenerator = (editCoverVersionId = null) => render(
    <MantineProvider>
        <ThumbnailGenerator
            editCoverVersionId={editCoverVersionId}
            workspaceId="workspace-1"
            projectId="project-1"
        />
    </MantineProvider>,
);

const deferred = () => {
    let resolve;
    const promise = new Promise((resolvePromise) => {
        resolve = resolvePromise;
    });
    return { promise, resolve };
};

describe('ThumbnailGenerator canvas load lifecycle', () => {
    beforeEach(() => {
        mocks.hydrateCoverCanvas.mockReset();
        mocks.serializeCoverCanvas.mockClear();
        mocks.useCoverDraft.mockClear();
        mocks.useCoverEditor.mockClear();
        mocks.useCoverVersions.mockClear();
        mocks.state.clearDraftCanvas = vi.fn();
        mocks.state.draftState = {
            clearCanvas: mocks.state.clearDraftCanvas,
            draftError: null,
            draftSavedAt: null,
        };
        mocks.state.loadCanvas = null;
        mocks.state.loadVersion = vi.fn();
        mocks.state.editor = createEditor(vi.fn());
    });

    afterEach(() => {
        cleanup();
    });

    it('ignores a pending load after clear while allowing an uncancelled load to replace the canvas', async () => {
        const pendingHydrate = deferred();
        const staleCanvas = { version_id: 'version-old' };
        const staleHydratedCanvas = { backgroundColor: '#101010', elements: [{ id: 'old' }] };
        mocks.hydrateCoverCanvas.mockReturnValue(pendingHydrate.promise);

        renderGenerator();
        let pendingLoad;
        await act(async () => {
            pendingLoad = mocks.state.loadCanvas(staleCanvas);
        });

        fireEvent.click(screen.getByRole('button', { name: 'delete canvas' }));
        expect(mocks.state.clearDraftCanvas).toHaveBeenCalledTimes(1);

        await act(async () => {
            pendingHydrate.resolve(staleHydratedCanvas);
            await pendingLoad;
        });

        expect(mocks.state.editor.replaceCanvas).not.toHaveBeenCalled();

        cleanup();
        const replacement = vi.fn();
        mocks.state.editor = createEditor(replacement);
        const currentHydrate = deferred();
        const currentCanvas = { version_id: 'version-current' };
        const currentHydratedCanvas = { backgroundColor: '#202020', elements: [{ id: 'current' }] };
        mocks.hydrateCoverCanvas.mockReturnValue(currentHydrate.promise);

        renderGenerator();
        let currentLoad;
        await act(async () => {
            currentLoad = mocks.state.loadCanvas(currentCanvas);
        });
        await act(async () => {
            currentHydrate.resolve(currentHydratedCanvas);
            await currentLoad;
        });

        expect(replacement).toHaveBeenCalledWith(currentHydratedCanvas);
    });

    it('loads an explicit version once, leaves ordinary entry blank, and follows a changed version id', async () => {
        renderGenerator();
        await act(async () => {});
        expect(mocks.state.loadVersion).not.toHaveBeenCalled();

        cleanup();
        mocks.state.editor = createEditor(vi.fn());
        const view = renderGenerator('version-a');
        await act(async () => {});
        expect(mocks.state.loadVersion).toHaveBeenCalledTimes(1);
        expect(mocks.state.loadVersion).toHaveBeenCalledWith('version-a');

        view.rerender(
            <MantineProvider>
                <ThumbnailGenerator
                    editCoverVersionId="version-a"
                    workspaceId="workspace-1"
                    projectId="project-1"
                />
            </MantineProvider>,
        );
        await act(async () => {});
        expect(mocks.state.loadVersion).toHaveBeenCalledTimes(1);

        view.rerender(
            <MantineProvider>
                <ThumbnailGenerator
                    editCoverVersionId="version-b"
                    workspaceId="workspace-1"
                    projectId="project-1"
                />
            </MantineProvider>,
        );
        await act(async () => {});
        expect(mocks.state.loadVersion).toHaveBeenCalledTimes(2);
        expect(mocks.state.loadVersion).toHaveBeenLastCalledWith('version-b');
    });
});

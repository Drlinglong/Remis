import { useCallback, useEffect, useRef, useState } from 'react';
import {
    createEmptyCoverCanvas,
    hydrateCoverCanvas,
    readCoverDraft,
    serializeCoverCanvas,
    writeCoverDraft,
} from './coverCanvasState';

const sameCanvas = (left, right) => JSON.stringify(left) === JSON.stringify(right);

export const useCoverDraft = ({
    workspaceId,
    projectId,
    canvasState,
    replaceCanvas,
    storage = window.localStorage,
}) => {
    const [restored, setRestored] = useState(false);
    const [draftSavedAt, setDraftSavedAt] = useState(null);
    const [draftError, setDraftError] = useState(null);
    const replaceCanvasRef = useRef(replaceCanvas);
    const saveGenerationRef = useRef(0);
    const restoreGenerationRef = useRef(0);
    const awaitingRestoredCanvasRef = useRef(null);
    const clearPendingRef = useRef(false);
    replaceCanvasRef.current = replaceCanvas;

    useEffect(() => {
        const restoreGeneration = restoreGenerationRef.current + 1;
        restoreGenerationRef.current = restoreGeneration;
        saveGenerationRef.current += 1;
        awaitingRestoredCanvasRef.current = null;
        clearPendingRef.current = false;
        setRestored(false);
        setDraftSavedAt(null);

        const restoreDraft = async () => {
            try {
                const persisted = readCoverDraft(storage, { workspaceId, projectId });
                const serialized = persisted || createEmptyCoverCanvas();
                const hydrated = await hydrateCoverCanvas(serialized);
                if (restoreGeneration !== restoreGenerationRef.current) return;
                awaitingRestoredCanvasRef.current = serialized;
                replaceCanvasRef.current(hydrated);
                setDraftError(null);
                setRestored(true);
            } catch (error) {
                if (restoreGeneration === restoreGenerationRef.current) {
                    setDraftError(error);
                }
            }
        };

        restoreDraft();
        return () => {
            if (restoreGeneration === restoreGenerationRef.current) {
                restoreGenerationRef.current += 1;
            }
        };
    }, [projectId, storage, workspaceId]);

    const clearCanvas = useCallback(() => {
        const emptyCanvas = createEmptyCoverCanvas();
        restoreGenerationRef.current += 1;
        saveGenerationRef.current += 1;
        awaitingRestoredCanvasRef.current = null;
        clearPendingRef.current = true;
        try {
            writeCoverDraft(storage, { workspaceId, projectId }, emptyCanvas);
            setDraftSavedAt(new Date());
            setDraftError(null);
            setRestored(true);
        } catch (error) {
            setDraftError(error);
        }
        replaceCanvasRef.current(emptyCanvas);
    }, [projectId, storage, workspaceId]);

    useEffect(() => {
        if (!restored) return undefined;
        const canvas = serializeCoverCanvas(canvasState);
        if (awaitingRestoredCanvasRef.current) {
            if (!sameCanvas(canvas, awaitingRestoredCanvasRef.current)) return undefined;
            awaitingRestoredCanvasRef.current = null;
        }
        const isBlank = canvas.backgroundColor === '#ffffff'
            && !canvas.backgroundImage
            && canvas.elements.length === 0;
        if (clearPendingRef.current) {
            if (!isBlank) return undefined;
            clearPendingRef.current = false;
        }
        const saveGeneration = saveGenerationRef.current;
        const timer = window.setTimeout(() => {
            if (saveGeneration !== saveGenerationRef.current) return;
            try {
                writeCoverDraft(storage, { workspaceId, projectId }, canvas);
                setDraftSavedAt(new Date());
                setDraftError(null);
            } catch (error) {
                setDraftError(error);
            }
        }, 600);
        return () => window.clearTimeout(timer);
    }, [canvasState, projectId, restored, storage, workspaceId]);

    return { restored, draftSavedAt, draftError, clearCanvas };
};

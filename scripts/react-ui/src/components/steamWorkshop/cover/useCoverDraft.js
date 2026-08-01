import { useCallback, useEffect, useRef, useState } from 'react';
import {
    createEmptyCoverCanvas,
    serializeCoverCanvas,
    writeCoverDraft,
} from './coverCanvasState';

export const useCoverDraft = ({
    workspaceId,
    projectId,
    canvasState,
    replaceCanvas,
    storage = window.localStorage,
}) => {
    const restored = true;
    const [draftSavedAt, setDraftSavedAt] = useState(null);
    const [draftError, setDraftError] = useState(null);
    const replaceCanvasRef = useRef(replaceCanvas);
    const saveGenerationRef = useRef(0);
    const clearPendingRef = useRef(false);
    const hasMountedRef = useRef(false);
    replaceCanvasRef.current = replaceCanvas;

    useEffect(() => {
        if (!hasMountedRef.current) {
            hasMountedRef.current = true;
            return undefined;
        }

        saveGenerationRef.current += 1;
        clearPendingRef.current = true;
        replaceCanvasRef.current(createEmptyCoverCanvas());
        return undefined;
    }, [projectId, storage, workspaceId]);

    const clearCanvas = useCallback(() => {
        const emptyCanvas = createEmptyCoverCanvas();
        saveGenerationRef.current += 1;
        clearPendingRef.current = true;
        try {
            writeCoverDraft(storage, { workspaceId, projectId }, emptyCanvas);
            setDraftSavedAt(new Date());
            setDraftError(null);
        } catch (error) {
            setDraftError(error);
        }
        replaceCanvasRef.current(emptyCanvas);
    }, [projectId, storage, workspaceId]);

    useEffect(() => {
        if (!restored) return undefined;
        const canvas = serializeCoverCanvas(canvasState);
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

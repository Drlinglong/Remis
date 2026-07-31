import { useEffect, useRef, useState } from 'react';
import {
    hydrateCoverCanvas,
    readCoverDraft,
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
    const [restored, setRestored] = useState(false);
    const [draftSavedAt, setDraftSavedAt] = useState(null);
    const [draftError, setDraftError] = useState(null);
    const replaceCanvasRef = useRef(replaceCanvas);
    replaceCanvasRef.current = replaceCanvas;

    useEffect(() => {
        let cancelled = false;
        setRestored(false);
        const restore = async () => {
            try {
                const stored = readCoverDraft(storage, { workspaceId, projectId });
                if (stored) {
                    const hydrated = await hydrateCoverCanvas(stored);
                    if (!cancelled) replaceCanvasRef.current(hydrated);
                }
            } catch {
                // A corrupt local draft must not prevent the editor from opening.
            } finally {
                if (!cancelled) setRestored(true);
            }
        };
        restore();
        return () => {
            cancelled = true;
        };
    }, [projectId, storage, workspaceId]);

    useEffect(() => {
        if (!restored) return undefined;
        const timer = window.setTimeout(() => {
            const canvas = serializeCoverCanvas(canvasState);
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

    return { restored, draftSavedAt, draftError };
};

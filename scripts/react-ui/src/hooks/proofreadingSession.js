import {
    applyProofreadingDraftPatches,
    getProofreadingDraftPatches,
} from '../components/proofreading/proofreadingEntryState';

export const PROOFREADING_SESSION_KEY = 'remis_proofreading_session_v1';

export const readProofreadingSession = (storage = sessionStorage) => {
    try {
        const raw = storage.getItem(PROOFREADING_SESSION_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return parsed?.version === 1 ? parsed : null;
    } catch {
        return null;
    }
};

export const writeProofreadingSession = (snapshot, storage = sessionStorage) => {
    try {
        storage.setItem(PROOFREADING_SESSION_KEY, JSON.stringify({
            version: 1,
            updatedAt: Date.now(),
            ...snapshot,
        }));
        return true;
    } catch {
        return false;
    }
};

export const clearProofreadingSession = (storage = sessionStorage) => {
    try {
        storage.removeItem(PROOFREADING_SESSION_KEY);
    } catch {
        // Storage may be unavailable in hardened browser contexts.
    }
};

export const createProofreadingSessionSnapshot = ({
    fileInfo,
    documentRevision,
    rows,
    query = '',
    filter = 'all',
    focusedEntryKey = null,
    scrollOffset = 0,
}) => ({
    projectId: fileInfo?.project_id || null,
    fileId: fileInfo?.file_id || null,
    documentRevision: documentRevision || null,
    patches: getProofreadingDraftPatches(rows || []),
    query,
    filter,
    focusedEntryKey,
    scrollOffset: Number.isFinite(scrollOffset) ? scrollOffset : 0,
});

export const restoreProofreadingRows = ({ rows, documentRevision, snapshot }) => {
    if (!snapshot?.patches?.length) {
        return { rows, status: 'clean' };
    }
    if (!snapshot.documentRevision || snapshot.documentRevision !== documentRevision) {
        return { rows, status: 'conflict' };
    }
    return {
        rows: applyProofreadingDraftPatches(rows, snapshot.patches),
        status: 'restored',
    };
};

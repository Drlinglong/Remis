import { useCallback, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import { isProofreadingRowChanged } from '../components/proofreading/proofreadingEntryState';
import {
    clearProofreadingSession,
    readProofreadingSession,
    restoreProofreadingRows,
} from './proofreadingSession';

/**
 * Canonical proofreading document state.
 * Entry rows are the only editable source of truth; the legacy raw-editor path is gone.
 */
export const useEditorContent = () => {
    const { t } = useTranslation();
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(false);
    const [fileInfo, setFileInfo] = useState(null);
    const [documentRevision, setDocumentRevision] = useState(null);
    const [draftRestoreStatus, setDraftRestoreStatus] = useState('clean');
    const [draftConflict, setDraftConflict] = useState(null);
    const [externalChangeDetected, setExternalChangeDetected] = useState(null);
    const loadRequestRef = useRef(0);
    const revisionRequestRef = useRef(0);

    const getRowsAsSaveEntries = useCallback(() => rows
        .filter(row => row.row_type === 'translation' && row.key)
        .map(row => ({ key: row.key, value: row.final_value || '' })), [rows]);

    const getStructurePatches = useCallback(() => rows
        .filter(row => (
            row.row_type === 'structure'
            && row.editable
            && row.final_value !== row.baseline_value
        ))
        .map(row => ({
            entry_id: row.entry_id,
            line_start: row.line_start,
            line_end: row.line_end,
            content: row.final_value || '',
        })), [rows]);

    const translationChangeCount = useMemo(() => rows.filter(row => (
        row.row_type === 'translation' && isProofreadingRowChanged(row)
    )).length, [rows]);
    const commentChangeCount = useMemo(() => getStructurePatches().length, [getStructurePatches]);
    const isDirty = translationChangeCount > 0 || commentChangeCount > 0;

    const updateRowFinalValue = useCallback((entryId, value) => {
        setRows(currentRows => currentRows.map(row => (
            row.entry_id === entryId ? { ...row, final_value: value } : row
        )));
    }, []);

    const settleSavedRows = useCallback((newRevision, keepStructureChanges = true) => {
        setRows(currentRows => currentRows.map(row => {
            if (!row.editable) return row;
            const finalValue = row.row_type === 'structure' && !keepStructureChanges
                ? row.baseline_value
                : row.final_value;
            return { ...row, final_value: finalValue, baseline_value: finalValue };
        }));
        setDocumentRevision(newRevision || documentRevision);
        setDraftRestoreStatus('clean');
        setDraftConflict(null);
        setExternalChangeDetected(null);
        clearProofreadingSession();
    }, [documentRevision]);

    const discardCurrentDraft = useCallback(() => {
        setRows(currentRows => currentRows.map(row => (
            row.editable ? { ...row, final_value: row.baseline_value } : row
        )));
        setDraftRestoreStatus('clean');
        setDraftConflict(null);
        clearProofreadingSession();
    }, []);

    const dismissDraftConflict = useCallback(() => {
        setDraftConflict(null);
        setDraftRestoreStatus('clean');
        clearProofreadingSession();
    }, []);

    const getProofreadingLoadErrorMessage = useCallback((detail) => {
        const fallback = typeof detail === 'string' && detail ? detail : 'Failed to load file data.';
        if (!detail || typeof detail !== 'object' || !detail.code) return fallback;
        const defaults = {
            project_not_found: 'Cannot load proofreading data because the project no longer exists.',
            file_not_indexed: 'Cannot load proofreading data because this file is not in the current project file index.',
            file_path_missing: 'Cannot load proofreading data because this project file has no recorded localization path.',
            file_path_not_found: detail.message || 'Cannot load proofreading data because the indexed file no longer exists.',
            data_preparation_failed: 'Cannot prepare proofreading data for this file.',
        };
        return t(`proofreading.errors.${detail.code}`, {
            defaultValue: detail.message || defaults[detail.code] || fallback,
        });
    }, [t]);

    const loadEditorData = useCallback(async (projectId, fileId) => {
        const requestId = ++loadRequestRef.current;
        revisionRequestRef.current += 1;
        setLoading(true);
        setDraftConflict(null);
        setDraftRestoreStatus('clean');
        setExternalChangeDetected(null);
        try {
            const response = await api.get(`/api/proofread/${projectId}/${fileId}`);
            if (requestId !== loadRequestRef.current) return;

            const data = response.data;
            const revision = data.document_revision || null;
            const baselineRows = (data.rows || []).map(row => ({
                ...row,
                baseline_value: row.final_value,
            }));
            const snapshot = readProofreadingSession();
            const matchingSnapshot = snapshot
                && snapshot.projectId === projectId
                && snapshot.fileId === fileId
                ? snapshot
                : null;
            const restored = restoreProofreadingRows({
                rows: baselineRows,
                documentRevision: revision,
                snapshot: matchingSnapshot,
            });

            setFileInfo({ path: data.file_path, project_id: projectId, file_id: fileId });
            setDocumentRevision(revision);
            setRows(restored.rows);
            setDraftRestoreStatus(restored.status);
            if (restored.status === 'conflict') {
                setDraftConflict(matchingSnapshot);
            }
        } catch (error) {
            if (requestId !== loadRequestRef.current) return;
            console.error('Failed to load proofreading data', error);
            const detail = error.response?.data?.detail;
            notifications.show({
                title: t('proofreading.notifications.error'),
                message: getProofreadingLoadErrorMessage(detail),
                color: 'red',
            });
        } finally {
            if (requestId === loadRequestRef.current) setLoading(false);
        }
    }, [getProofreadingLoadErrorMessage, t]);

    const checkExternalRevision = useCallback(async () => {
        if (!fileInfo || !documentRevision) return false;
        const requestId = ++revisionRequestRef.current;
        const checkedFile = fileInfo;
        try {
            const response = await api.get(
                `/api/proofread/${checkedFile.project_id}/${checkedFile.file_id}/revision`
            );
            if (requestId !== revisionRequestRef.current) return false;
            const diskRevision = response.data?.document_revision || null;
            if (diskRevision && diskRevision !== documentRevision) {
                setExternalChangeDetected({
                    loadedRevision: documentRevision,
                    diskRevision,
                });
                return true;
            }
            setExternalChangeDetected(null);
            return false;
        } catch (error) {
            console.warn('Failed to check proofreading file revision', error);
            return false;
        }
    }, [documentRevision, fileInfo]);

    const clearEditorData = useCallback(() => {
        loadRequestRef.current += 1;
        revisionRequestRef.current += 1;
        setRows([]);
        setFileInfo(null);
        setDocumentRevision(null);
        setDraftRestoreStatus('clean');
        setDraftConflict(null);
        setExternalChangeDetected(null);
        setLoading(false);
    }, []);

    return {
        rows,
        loading,
        fileInfo,
        documentRevision,
        draftRestoreStatus,
        draftConflict,
        externalChangeDetected,
        translationChangeCount,
        commentChangeCount,
        isDirty,
        updateRowFinalValue,
        getRowsAsSaveEntries,
        getStructurePatches,
        settleSavedRows,
        discardCurrentDraft,
        dismissDraftConflict,
        loadEditorData,
        checkExternalRevision,
        clearEditorData,
    };
};

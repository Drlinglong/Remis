import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import { toParadoxLang } from '../utils/paradoxMapping';
import { getBracketVariableWarnings } from '../components/proofreading/proofreadingEntryState';
import { useFileNavigation } from './useFileNavigation';
import { useEditorContent } from './useEditorContent';
import {
    createProofreadingSessionSnapshot,
    readProofreadingSession,
    writeProofreadingSession,
} from './proofreadingSession';

/** Lean coordinator for navigation, document state, validation, and save flow. */
const useProofreadingState = () => {
    const { t } = useTranslation();
    const initialSessionRef = useRef(readProofreadingSession());
    const navigation = useFileNavigation();
    const editor = useEditorContent();
    const { fileInfo, loadEditorData, clearEditorData } = editor;

    const [validationResults, setValidationResults] = useState([]);
    const [saving, setSaving] = useState(false);
    const [stats, setStats] = useState({ error: 0, warning: 0 });
    const [saveModalOpen, setSaveModalOpen] = useState(false);
    const [variableWarnings, setVariableWarnings] = useState([]);
    const [validating, setValidating] = useState(false);
    const [query, setQuery] = useState(initialSessionRef.current?.query || '');
    const [filter, setFilter] = useState(initialSessionRef.current?.filter || 'all');
    const [focusedEntryKey, setFocusedEntryKey] = useState(initialSessionRef.current?.focusedEntryKey || null);
    const [scrollOffset, setScrollOffset] = useState(initialSessionRef.current?.scrollOffset || 0);
    const [focusEntryKey, setFocusEntryKey] = useState(initialSessionRef.current?.focusedEntryKey || null);
    const pendingAfterSaveRef = useRef(null);
    const handledDeepLinkRef = useRef(null);

    const clearValidation = useCallback(() => {
        setValidationResults([]);
        setStats({ error: 0, warning: 0 });
    }, []);

    const handleProjectSelect = useCallback((projectId) => {
        clearEditorData();
        clearValidation();
        navigation.handleProjectSelect(projectId);
    }, [clearEditorData, clearValidation, navigation]);

    useEffect(() => {
        if (navigation.selectedProject && !navigation.currentSourceFile) {
            clearEditorData();
            clearValidation();
            return;
        }
        if (!navigation.selectedProject || !navigation.currentSourceFile) return;

        const requestedFileId = navigation.currentTargetFile
            ? navigation.currentTargetFile.file_id
            : navigation.currentSourceFile.file_id;
        if (fileInfo
            && fileInfo.project_id === navigation.selectedProject.project_id
            && fileInfo.file_id === requestedFileId) return;

        clearValidation();
        loadEditorData(navigation.selectedProject.project_id, requestedFileId);
    }, [
        navigation.selectedProject,
        navigation.currentSourceFile,
        navigation.currentTargetFile,
        loadEditorData,
        clearEditorData,
        clearValidation,
        fileInfo,
    ]);

    const persistSessionNow = useCallback(() => {
        if (!fileInfo || editor.draftConflict) return false;
        return writeProofreadingSession(createProofreadingSessionSnapshot({
            fileInfo,
            documentRevision: editor.documentRevision,
            rows: editor.rows,
            query,
            filter,
            focusedEntryKey,
            scrollOffset,
        }));
    }, [
        editor.documentRevision,
        editor.draftConflict,
        editor.rows,
        fileInfo,
        filter,
        focusedEntryKey,
        query,
        scrollOffset,
    ]);

    useEffect(() => {
        if (!fileInfo || editor.draftConflict) return undefined;
        const timer = setTimeout(persistSessionNow, 350);
        return () => clearTimeout(timer);
    }, [editor.draftConflict, fileInfo, persistSessionNow]);

    useEffect(() => {
        const targetKey = navigation.searchParams.get('entryKey');
        if (!targetKey || !fileInfo || !editor.rows.length) return;
        const identity = `${fileInfo.file_id}:${targetKey}`;
        if (handledDeepLinkRef.current === identity) return;
        handledDeepLinkRef.current = identity;

        if (editor.rows.some(row => row.row_type === 'translation' && row.key === targetKey)) {
            setQuery('');
            setFilter('all');
            setFocusedEntryKey(targetKey);
            setFocusEntryKey(targetKey);
        } else {
            notifications.show({
                title: t('proofreading.notifications.error'),
                message: t('proofreading.deep_link_missing', {
                    defaultValue: `The requested entry no longer exists: ${targetKey}`,
                    key: targetKey,
                }),
                color: 'yellow',
            });
        }
    }, [editor.rows, fileInfo, navigation.searchParams, t]);

    const updateRowFinalValue = useCallback((entryId, value) => {
        editor.updateRowFinalValue(entryId, value);
        clearValidation();
    }, [clearValidation, editor]);

    const handleValidate = useCallback(async () => {
        if (!navigation.selectedProject || !editor.rows.length) return;
        setValidating(true);
        clearValidation();
        try {
            const entries = editor.getRowsAsSaveEntries();
            const virtualContent = entries
                .map(entry => {
                    const key = /:\d+$/.test(entry.key) ? entry.key : `${entry.key}:0`;
                    const value = String(entry.value || '').replace(/"/g, '\\"');
                    return ` ${key} "${value}"`;
                })
                .join('\n');
            const response = await api.post('/api/validate/localization', {
                game_id: navigation.selectedProject.game_id || 'victoria3',
                content: virtualContent,
                source_lang_code: 'en_US',
            });
            const issues = (response.data || []).map(issue => {
                const lineIndex = Math.max(0, Number(issue.line_number || 1) - 1);
                return { ...issue, key: issue.key || entries[lineIndex]?.key || null };
            });
            setValidationResults(issues);
            const errors = issues.filter(issue => issue.level === 'error').length;
            const warnings = issues.filter(issue => issue.level === 'warning').length;
            setStats({ error: errors, warning: warnings });
            notifications.show({
                title: errors || warnings
                    ? t('proofreading.notifications.issues_found')
                    : t('proofreading.notifications.perfect'),
                message: errors || warnings
                    ? t('proofreading.notifications.issues_found_message', { errors, warnings })
                    : t('proofreading.notifications.perfect_message'),
                color: errors || warnings ? 'yellow' : 'green',
            });
        } catch (error) {
            console.error('Validation failed', error);
            notifications.show({
                title: t('proofreading.notifications.error'),
                message: t('proofreading.notifications.validation_failed'),
                color: 'red',
            });
        } finally {
            setValidating(false);
        }
    }, [clearValidation, editor, navigation.selectedProject, t]);

    const confirmSave = useCallback(async (includeStructureChanges = true) => {
        setSaveModalOpen(false);
        setSaving(true);
        try {
            const savePayload = {
                project_id: editor.fileInfo.project_id,
                file_id: editor.fileInfo.file_id,
                base_revision: editor.documentRevision,
                entries: editor.getRowsAsSaveEntries().map(entry => ({
                    key: entry.key,
                    translation: entry.value,
                })),
                structure_patches: includeStructureChanges ? editor.getStructurePatches() : [],
                target_language: `l_${toParadoxLang(navigation.selectedProject.source_language || 'english')}`,
            };
            const response = await api.post('/api/proofread/save', savePayload);
            editor.settleSavedRows(response.data?.document_revision, includeStructureChanges);
            clearValidation();
            setVariableWarnings([]);
            notifications.show({
                title: t('proofreading.notifications.saved'),
                message: t('proofreading.notifications.saved_message'),
                color: 'green',
            });
            const afterSave = pendingAfterSaveRef.current;
            pendingAfterSaveRef.current = null;
            if (afterSave) afterSave();
            return true;
        } catch (error) {
            console.error('Save failed', error);
            const conflict = error.response?.status === 409;
            notifications.show({
                title: t('proofreading.notifications.error'),
                message: conflict
                    ? t('proofreading.save_conflict', {
                        defaultValue: 'The file changed on disk. Your draft was not overwritten; reload and review the conflict.',
                    })
                    : t('proofreading.notifications.save_failed'),
                color: 'red',
            });
            return false;
        } finally {
            setSaving(false);
        }
    }, [clearValidation, editor, navigation.selectedProject, t]);

    const requestSave = useCallback((afterSave = null) => {
        if (!editor.fileInfo || !editor.isDirty) return;
        pendingAfterSaveRef.current = afterSave;
        const warnings = getBracketVariableWarnings(editor.rows);
        setVariableWarnings(warnings);
        if (warnings.length || editor.commentChangeCount > 0) {
            setSaveModalOpen(true);
        } else {
            confirmSave(true);
        }
    }, [confirmSave, editor.commentChangeCount, editor.fileInfo, editor.isDirty, editor.rows]);

    const cancelSave = useCallback(() => {
        pendingAfterSaveRef.current = null;
        setSaveModalOpen(false);
    }, []);

    const discardCurrentDraft = useCallback(() => {
        pendingAfterSaveRef.current = null;
        setVariableWarnings([]);
        clearValidation();
        editor.discardCurrentDraft();
    }, [clearValidation, editor]);

    const requestFocusEntry = useCallback((key) => {
        if (!key) return;
        setQuery('');
        setFilter('all');
        setFocusedEntryKey(key);
        setFocusEntryKey(null);
        requestAnimationFrame(() => setFocusEntryKey(key));
    }, []);

    const handleOpenFolder = useCallback(async () => {
        if (!editor.fileInfo?.path) return;
        try {
            const path = editor.fileInfo.path.replace(/\\/g, '/');
            await api.post('/api/system/open_folder', { path: path.substring(0, path.lastIndexOf('/')) });
            notifications.show({
                title: t('proofreading.notifications.folder_opened'),
                message: t('proofreading.notifications.folder_opened'),
                color: 'green',
            });
        } catch {
            notifications.show({
                title: t('proofreading.notifications.error'),
                message: t('proofreading.notifications.folder_failed'),
                color: 'red',
            });
        }
    }, [editor.fileInfo, t]);

    return {
        ...navigation,
        ...editor,
        handleProjectSelect,
        updateRowFinalValue,
        validationResults,
        stats,
        saving,
        saveModalOpen,
        variableWarnings,
        handleValidate,
        requestSave,
        confirmSave,
        cancelSave,
        discardCurrentDraft,
        handleOpenFolder,
        validating,
        query,
        setQuery,
        filter,
        setFilter,
        focusedEntryKey,
        setFocusedEntryKey,
        focusEntryKey,
        requestFocusEntry,
        scrollOffset,
        setScrollOffset,
        persistSessionNow,
    };
};

export default useProofreadingState;

import { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import { toParadoxLang } from '../utils/paradoxMapping';
import { useFileNavigation } from './useFileNavigation';
import { useEditorContent } from './useEditorContent';
import { useLinter } from './useLinter';

/**
 * Lean coordinator hook for the Proofreading page.
 * Composes navigation, editor, and linter logic.
 */
const useProofreadingState = () => {
    const { t } = useTranslation();
    // Composition of child hooks
    const navigation = useFileNavigation();
    const editor = useEditorContent();
    const linter = useLinter();
    const { fileInfo, loadEditorData, clearEditorData } = editor;

    // ==================== Coordinator States ====================
    const [validationResults, setValidationResults] = useState([]);
    const [saving, setSaving] = useState(false);
    const [stats, setStats] = useState({ error: 0, warning: 0 });
    const [saveModalOpen, setSaveModalOpen] = useState(false);
    const [validating, setValidating] = useState(false);

    const formatVirtualEntry = useCallback((entry) => {
        const key = String(entry.key || '');
        const versionedKey = /:\d+$/.test(key) ? key : `${key}:0`;
        const value = String(entry.value || '').replace(/"/g, '\\"');
        return ` ${versionedKey} "${value}"\n`;
    }, []);

    const handleProjectSelect = useCallback((projectId) => {
        clearEditorData();
        setValidationResults([]);
        setStats({ error: 0, warning: 0 });
        navigation.handleProjectSelect(projectId);
    }, [clearEditorData, navigation]);

    // ==================== Coordinator Logic ====================

    // Wire up navigation change to editor loading
    useEffect(() => {
        if (navigation.selectedProject && !navigation.currentSourceFile) {
            clearEditorData();
            return;
        }

        if (navigation.selectedProject && navigation.currentSourceFile) {
            const requestedFileId = navigation.currentTargetFile
                ? navigation.currentTargetFile.file_id
                : navigation.currentSourceFile.file_id;

            // G U A R D: Check if we already have this file loaded
            if (fileInfo &&
                fileInfo.project_id === navigation.selectedProject.project_id &&
                fileInfo.file_id === requestedFileId) {
                return; // Already loaded, skip to prevent loop
            }

            // Only load if different
            loadEditorData(
                navigation.selectedProject.project_id,
                navigation.currentSourceFile.file_path,
                requestedFileId
            );
        }
    }, [
        navigation.selectedProject,
        navigation.currentSourceFile,
        navigation.currentTargetFile,
        loadEditorData,
        clearEditorData,
        fileInfo
    ]);

    const handleValidate = useCallback(async () => {
        if (!navigation.selectedProject) return;
        setValidating(true);
        setValidationResults([]);
        try {
            const parsed = editor.rows.length
                ? editor.getRowsAsSaveEntries()
                : editor.parseEditorContentToEntries(editor.finalContentStr);
            let virtualContent = "";
            parsed.forEach(e => {
                virtualContent += formatVirtualEntry(e);
            });

            const response = await api.post('/api/validate/localization', {
                game_id: navigation.selectedProject.game_id || 'victoria3',
                content: virtualContent,
                source_lang_code: 'en_US'
            });

            const issues = response.data;
            setValidationResults(issues);

            const errors = issues.filter(i => i.level === 'error').length;
            const warnings = issues.filter(i => i.level === 'warning').length;
            setStats({ error: errors, warning: warnings });

            if (errors === 0 && warnings === 0) {
                notifications.show({
                    title: t('proofreading.notifications.perfect'),
                    message: t('proofreading.notifications.perfect_message'),
                    color: 'green'
                });
            } else {
                notifications.show({
                    title: t('proofreading.notifications.issues_found'),
                    message: t('proofreading.notifications.issues_found_message', { errors, warnings }),
                    color: 'yellow'
                });
            }

        } catch (error) {
            console.error("Validation failed", error);
            notifications.show({ title: t('proofreading.notifications.error'), message: t('proofreading.notifications.validation_failed'), color: 'red' });
        } finally {
            setValidating(false);
        }
    }, [editor, formatVirtualEntry, navigation.selectedProject, t]);

    const confirmSave = useCallback(async (includeStructureChanges = true) => {
        setSaveModalOpen(false);
        setSaving(true);
        try {
            const parsedEntries = editor.rows.length
                ? editor.getRowsAsSaveEntries()
                : editor.parseEditorContentToEntries(editor.finalContentStr);

            const savePayload = {
                project_id: editor.fileInfo.project_id,
                file_id: editor.fileInfo.file_id,
                entries: parsedEntries.map(e => ({
                    key: e.key,
                    translation: e.value
                })),
                structure_patches: includeStructureChanges
                    ? editor.getStructurePatches()
                    : [],
                target_language: `l_${toParadoxLang(navigation.selectedProject.source_language || 'english')}`
            };

            await api.post('/api/proofread/save', savePayload);
            editor.settleStructureChanges(includeStructureChanges);
            notifications.show({ title: t('proofreading.notifications.saved'), message: t('proofreading.notifications.saved_message'), color: 'green' });

        } catch (error) {
            console.error("Save failed", error);
            notifications.show({ title: t('proofreading.notifications.error'), message: t('proofreading.notifications.save_failed'), color: 'red' });
        } finally {
            setSaving(false);
        }
    }, [editor, navigation.selectedProject, t]);

    const handleSaveClick = useCallback(() => {
        if (editor.keyChangeWarning || editor.commentChangeCount > 0) {
            setSaveModalOpen(true);
        } else {
            confirmSave();
        }
    }, [editor.keyChangeWarning, editor.commentChangeCount, confirmSave]);

    const handleOpenFolder = useCallback(async () => {
        if (!editor.fileInfo || !editor.fileInfo.path) return;
        try {
            const path = editor.fileInfo.path.replace(/\\/g, '/');
            const dirPath = path.substring(0, path.lastIndexOf('/'));
            await api.post('/api/system/open_folder', { path: dirPath });
            notifications.show({ title: t('proofreading.notifications.folder_opened'), message: t('proofreading.notifications.folder_opened'), color: 'green' });
        } catch {
            notifications.show({ title: t('proofreading.notifications.error'), message: t('proofreading.notifications.folder_failed'), color: 'red' });
        }
    }, [editor.fileInfo, t]);

    // ==================== Final Exposure ====================
    return {
        // From Navigation
        ...navigation,

        // From Editor
        ...editor,

        // From Linter
        ...linter,

        // Coordinator State/Logic
        handleProjectSelect,
        validationResults,
        stats,
        saving,
        saveModalOpen,
        setSaveModalOpen,
        handleValidate,
        handleSaveClick,
        confirmSave,
        handleOpenFolder,
        validating,
    };
};

export default useProofreadingState;

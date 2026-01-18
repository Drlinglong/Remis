import { useState, useCallback, useEffect } from 'react';
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
    // Composition of child hooks
    const navigation = useFileNavigation();
    const editor = useEditorContent();
    const linter = useLinter();

    // ==================== Coordinator States ====================
    const [validationResults, setValidationResults] = useState([]);
    const [saving, setSaving] = useState(false);
    const [stats, setStats] = useState({ error: 0, warning: 0 });
    const [saveModalOpen, setSaveModalOpen] = useState(false);
    const [validating, setValidating] = useState(false);

    // ==================== Coordinator Logic ====================

    // Wire up navigation change to editor loading
    useEffect(() => {
        if (navigation.selectedProject && navigation.currentSourceFile) {
            const requestedFileId = navigation.currentTargetFile
                ? navigation.currentTargetFile.file_id
                : navigation.currentSourceFile.file_id;

            // G U A R D: Check if we already have this file loaded
            if (editor.fileInfo &&
                editor.fileInfo.project_id === navigation.selectedProject.project_id &&
                editor.fileInfo.file_id === requestedFileId) {
                return; // Already loaded, skip to prevent loop
            }

            // Only load if different
            editor.loadEditorData(
                navigation.selectedProject.project_id,
                navigation.currentSourceFile.file_path,
                requestedFileId
            );
        }
    }, [
        navigation.selectedProject,
        navigation.currentSourceFile,
        navigation.currentTargetFile,
        editor.loadEditorData,
        editor.fileInfo // Add fileInfo to dependencies
    ]);

    const handleValidate = useCallback(async () => {
        if (!navigation.selectedProject) return;
        setValidating(true);
        setValidationResults([]);
        try {
            const parsed = editor.parseEditorContentToEntries(editor.finalContentStr);
            let virtualContent = "";
            parsed.forEach(e => {
                virtualContent += ` ${e.key}:0 "${e.value}"\n`;
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
                notifications.show({ title: 'Perfect', message: 'No issues found.', color: 'green' });
            } else {
                notifications.show({ title: 'Issues Found', message: `Found ${errors} errors and ${warnings} warnings.`, color: 'yellow' });
            }

        } catch (error) {
            console.error("Validation failed", error);
            notifications.show({ title: 'Error', message: "Validation failed.", color: 'red' });
        } finally {
            setValidating(false);
        }
    }, [editor, navigation.selectedProject]);

    const confirmSave = useCallback(async () => {
        setSaveModalOpen(false);
        setSaving(true);
        try {
            const parsedEntries = editor.parseEditorContentToEntries(editor.finalContentStr);

            const savePayload = {
                project_id: editor.fileInfo.project_id,
                file_id: editor.fileInfo.file_id,
                entries: parsedEntries.map(e => ({
                    key: e.key,
                    translation: e.value
                })),
                target_language: `l_${toParadoxLang(navigation.selectedProject.source_language || 'english')}`
            };

            await api.post('/api/proofread/save', savePayload);
            notifications.show({ title: 'Saved', message: 'File saved successfully.', color: 'green' });

        } catch (error) {
            console.error("Save failed", error);
            notifications.show({ title: 'Error', message: "Failed to save file.", color: 'red' });
        } finally {
            setSaving(false);
        }
    }, [editor, navigation.selectedProject]);

    const handleSaveClick = useCallback(() => {
        if (editor.keyChangeWarning) {
            setSaveModalOpen(true);
        } else {
            confirmSave();
        }
    }, [editor.keyChangeWarning, confirmSave]);

    const handleOpenFolder = useCallback(async () => {
        if (!editor.fileInfo || !editor.fileInfo.path) return;
        try {
            const path = editor.fileInfo.path.replace(/\\/g, '/');
            const dirPath = path.substring(0, path.lastIndexOf('/'));
            await api.post('/api/system/open_folder', { path: dirPath });
            notifications.show({ title: 'Success', message: 'Folder opened', color: 'green' });
        } catch (error) {
            notifications.show({ title: 'Error', message: 'Failed to open folder', color: 'red' });
        }
    }, [editor.fileInfo]);

    // ==================== Final Exposure ====================
    return {
        // From Navigation
        ...navigation,

        // From Editor
        ...editor,

        // From Linter
        ...linter,

        // Coordinator State/Logic
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

import { useState } from 'react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import { open } from '@tauri-apps/plugin-dialog';
import api from '../utils/api';

/**
 * Shared hook for deploy and fake localization cleanup workflows.
 * Used by both TaskRunner (post-translation) and ProjectHeader (project management).
 *
 * @param {Object} options
 * @param {Function} options.getOutputFolderName - Returns the output folder name for deploy
 * @param {string|null} options.projectId - Project ID
 * @param {string} options.gameId - Game ID (e.g. "victoria3")
 * @param {Function} [options.onDeploySuccess] - Callback on successful deploy
 * @param {Function} [options.onCleanSuccess] - Callback on successful clean
 */
export function useDeployActions({ getOutputFolderName, projectId, gameId, onDeploySuccess, onCleanSuccess }) {
    const { t } = useTranslation();

    // Modal state
    const [deployModalOpen, setDeployModalOpen] = useState(false);
    const [cleanModalOpen, setCleanModalOpen] = useState(false);
    const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

    // Path state
    const [deployPath, setDeployPath] = useState('');
    const [workshopPath, setWorkshopPath] = useState('');
    const [sourceLanguage, setSourceLanguage] = useState('english');

    // Loading state
    const [loading, setLoading] = useState(false);
    const [infoLoading, setInfoLoading] = useState(false);

    const applyDeployInfo = (data) => {
        setDeployPath(data.default_deploy_path || '');
        setWorkshopPath(data.detected_workshop_path || '');
        setSourceLanguage(data.source_language || 'english');
    };

    const fetchDeployInfo = async () => {
        setInfoLoading(true);
        try {
            const folderName = getOutputFolderName();
            const response = await api.post('/api/tools/deploy_info', {
                project_id: projectId || null,
                game_id: gameId || '',
                output_folder_name: folderName
            });
            applyDeployInfo(response.data);
            return response.data;
        } catch (error) {
            console.error("Failed to load deploy info:", error);
            notifications.show({
                title: t('deploy_failed_title'),
                message: t('deploy_error_load_info'),
                color: 'red'
            });
            return null;
        } finally {
            setInfoLoading(false);
        }
    };

    const handleOpenDeployModal = () => {
        setDeployModalOpen(true);
        fetchDeployInfo();
    };

    const handleOpenCleanModal = () => {
        setCleanModalOpen(true);
        fetchDeployInfo();
    };

    const getErrorMessage = (error) => {
        const detail = error.response?.data?.detail || error.message || '';
        if (detail.includes("Source directory not found")) {
            return t('deploy_error_source_not_found');
        }
        if (detail.includes("Original mod path does not exist")) {
            return t('deploy_error_original_not_found');
        }
        if (detail.includes("Could not determine Paradox mod folder")) {
            return t('deploy_error_paradox_dir_not_found');
        }
        return detail;
    };

    const handleDetectWorkshopPath = async () => {
        const data = await fetchDeployInfo();
        if (data?.detected_workshop_path) {
            notifications.show({
                title: t('deploy_detect_success_title'),
                message: t('deploy_detect_success_message'),
                color: 'green'
            });
            return;
        }

        notifications.show({
            title: t('deploy_detect_failed_title'),
            message: t('deploy_detect_failed_message'),
            color: 'yellow'
        });
    };

    const handleBrowseWorkshopPath = async () => {
        const selected = await open({
            directory: true,
            multiple: false,
            title: t('deploy_select_original_mod_folder')
        });

        if (typeof selected === 'string') {
            setWorkshopPath(selected);
        }
    };

    const handleExecuteDeploy = async () => {
        setLoading(true);
        try {
            const folderName = getOutputFolderName();
            const response = await api.post('/api/tools/deploy_mod', {
                project_id: projectId || null,
                output_folder_name: folderName,
                game_id: gameId,
                target_deploy_path: deployPath,
                clean_fake_loc: false,
                source_language: sourceLanguage
            });

            if (response.data.status === 'success') {
                notifications.show({ title: t('deploy_success_title'), message: t('deploy_success_message'), color: 'green' });
                setDeployModalOpen(false);
                onDeploySuccess?.();
            } else {
                notifications.show({ title: t('deploy_failed_title'), message: response.data.message || 'Deployment failed', color: 'red' });
            }
        } catch (error) {
            console.error("Deployment failed:", error);
            const errorMsg = getErrorMessage(error);
            notifications.show({ title: t('deploy_failed_title'), message: errorMsg, color: 'red' });
        } finally {
            setLoading(false);
        }
    };

    const handleExecuteClean = async () => {
        setConfirmDeleteOpen(false);
        setLoading(true);
        try {
            const response = await api.post('/api/tools/clean_fake_loc', {
                workshop_path: workshopPath,
                source_language: sourceLanguage
            });

            if (response.data.status === 'success' || response.data.status === 'partial_success' || response.data.status === 'warning') {
                let cleanMsg = t('deploy_clean_success_message');
                if (response.data.status === 'success' || response.data.status === 'partial_success') {
                    const fCount = response.data.removed_folders?.length || 0;
                    const fileCount = response.data.removed_files?.length || 0;
                    if (fCount === 0 && fileCount === 0) {
                        cleanMsg = t('deploy_clean_no_files_found');
                    } else {
                        cleanMsg += t('deploy_clean_files_removed', { folders: fCount, files: fileCount });
                    }
                } else if (response.data.status === 'warning') {
                    cleanMsg = `${cleanMsg} (Warning: ${response.data.message})`;
                }
                notifications.show({ title: t('deploy_clean_success_title'), message: cleanMsg, color: 'green' });
                setCleanModalOpen(false);
                onCleanSuccess?.();
            } else {
                notifications.show({ title: t('deploy_failed_title'), message: response.data.message || 'Cleanup failed', color: 'red' });
            }
        } catch (error) {
            console.error("Cleanup failed:", error);
            const errorMsg = getErrorMessage(error);
            notifications.show({ title: t('deploy_failed_title'), message: errorMsg, color: 'red' });
        } finally {
            setLoading(false);
        }
    };

    return {
        // Modal state
        deployModalOpen, setDeployModalOpen,
        cleanModalOpen, setCleanModalOpen,
        confirmDeleteOpen, setConfirmDeleteOpen,
        // Path state
        deployPath, setDeployPath,
        workshopPath, setWorkshopPath,
        // Loading state
        loading, infoLoading,
        // Actions
        handleOpenDeployModal,
        handleOpenCleanModal,
        handleDetectWorkshopPath,
        handleBrowseWorkshopPath,
        handleExecuteDeploy,
        handleExecuteClean,
    };
}

import React, { useState } from 'react';
import { Paper, Group, Text, Button, Modal, Stack, TextInput, ActionIcon, Tooltip, Divider } from '@mantine/core';
import { IconFolder, IconPlus, IconTrash, IconExternalLink } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { open } from '@tauri-apps/plugin-dialog';
import api from '../../utils/api';
import styles from '../../pages/ProjectManagement.module.css';

const ProjectPathManager = ({ projectDetails, onPathsUpdated }) => {
    const { t } = useTranslation();
    const [managePathsOpen, setManagePathsOpen] = useState(false);
    const [sourcePath, setSourcePath] = useState('');
    const [translationDirs, setTranslationDirs] = useState([]);
    const [newDirPath, setNewDirPath] = useState('');

    const handleOpenManagePaths = () => {
        setSourcePath(projectDetails.source_path || '');
        setTranslationDirs(projectDetails.translation_dirs || []);
        setManagePathsOpen(true);
    };

    const handleBrowseSourcePath = async () => {
        try {
            const selected = await open({
                directory: true,
                multiple: false,
                title: t('project_management.manage_paths.source_placeholder')
            });
            if (selected && typeof selected === 'string') {
                setSourcePath(selected);
            }
        } catch (err) {
            console.error('Failed to open source browse dialog:', err);
        }
    };

    const handleBrowseTranslationPath = async () => {
        try {
            const selected = await open({
                directory: true,
                multiple: false,
                title: t('project_management.manage_paths.placeholder')
            });
            if (selected && typeof selected === 'string') {
                setNewDirPath(selected);
            }
        } catch (err) {
            console.error('Failed to open translation browse dialog:', err);
        }
    };

    const handleAddDir = () => {
        if (newDirPath && !translationDirs.includes(newDirPath)) {
            setTranslationDirs([...translationDirs, newDirPath]);
            setNewDirPath('');
        }
    };

    const handleRemoveDir = (index) => {
        setTranslationDirs(translationDirs.filter((_, i) => i !== index));
    };

    const handleSavePaths = async () => {
        try {
            const response = await api.post(`/api/project/${projectDetails.project_id}/config`, {
                source_path: sourcePath,
                translation_dirs: translationDirs
            });
            console.log('Save response:', response.data);
            setManagePathsOpen(false);
            if (onPathsUpdated) {
                onPathsUpdated();
            }
        } catch (error) {
            console.error('Failed to save paths:', error);
            alert(`Failed to save project paths: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleOpenFolder = async (path) => {
        if (!path) return;
        try {
            await api.post('/api/system/open_folder', { path });
        } catch (error) {
            console.error("Failed to open folder", error);
            alert(`Failed to open folder: ${error.message}`);
        }
    };

    return (
        <>
            <Paper withBorder p="md" radius="md" className={styles.glassCard}>
                <Group justify="space-between">
                    <div>
                        <Group gap={4}>
                            <Text size="sm" fw={500}>{t('project_management.source_dir')}:</Text>
                            <ActionIcon size="xs" variant="transparent" onClick={() => handleOpenFolder(projectDetails.source_path)} title={t('project_management.open_source_dir')}>
                                <IconExternalLink size={14} />
                            </ActionIcon>
                        </Group>
                        <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>{projectDetails.source_path || 'Loading...'}</Text>
                    </div>
                    <div>
                        <Group gap={4}>
                            <Text size="sm" fw={500}>{t('project_management.translation_dir')}:</Text>
                            {projectDetails.translation_dirs && projectDetails.translation_dirs.length > 0 && (
                                <ActionIcon size="xs" variant="transparent" onClick={() => handleOpenFolder(projectDetails.translation_dirs[0])} title={t('project_management.open_translation_dir')}>
                                    <IconExternalLink size={14} />
                                </ActionIcon>
                            )}
                        </Group>
                        <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                            {projectDetails.translation_dirs ? projectDetails.translation_dirs.join(', ') : 'Default'}
                        </Text>
                    </div>
                    <Tooltip label={t('project_management.tooltip_manage_paths')}>
                        <Button
                            id="manage-paths-btn"
                            variant="outline"
                            size="xs"
                            onClick={handleOpenManagePaths}
                        >
                            {t('project_management.manage_paths_button')}
                        </Button>
                    </Tooltip>
                </Group>
            </Paper>

            <Modal
                opened={managePathsOpen}
                onClose={() => setManagePathsOpen(false)}
                title={t('project_management.manage_paths.title')}
                size="lg"
            >
                <Stack gap="lg">
                    {/* Section 1: Source file directory (Single) */}
                    <div>
                        <Text size="sm" fw={600} mb="xs" c="blue">
                            {t('project_management.manage_paths.source_section')} (1)
                        </Text>
                        <Text size="xs" c="dimmed" mb="sm">
                            {t('project_management.manage_paths.source_desc')}
                        </Text>
                        <Group align="flex-end">
                            <TextInput
                                placeholder={t('project_management.manage_paths.source_placeholder')}
                                value={sourcePath}
                                onChange={(e) => setSourcePath(e.currentTarget.value)}
                                style={{ flex: 1 }}
                            />
                            <Button onClick={handleBrowseSourcePath} leftSection={<IconFolder size={16} />}>
                                {t('project_management.manage_paths.browse')}
                            </Button>
                        </Group>
                    </div>

                    <Divider />

                    {/* Section 2: Translation output directories (Multiple) */}
                    <div>
                        <Text size="sm" fw={600} mb="xs" c="teal">
                            {t('project_management.manage_paths.translation_section')}
                        </Text>
                        <Text size="xs" c="dimmed" mb="sm">
                            {t('project_management.manage_paths.translation_desc')}
                        </Text>
                        
                        <Stack gap="xs" mb="md">
                            {translationDirs.length === 0 ? (
                                <Text size="sm" c="dimmed" italic>{t('project_management.manage_paths.no_dirs')}</Text>
                            ) : (
                                translationDirs.map((dir, index) => (
                                    <Paper key={index} withBorder p="xs" radius="sm" style={{ background: 'rgba(0,0,0,0.1)' }}>
                                        <Group justify="space-between">
                                            <Text size="sm" style={{ flex: 1, wordBreak: 'break-all' }}>{dir}</Text>
                                            <ActionIcon color="red" variant="subtle" onClick={() => handleRemoveDir(index)}>
                                                <IconTrash size={16} />
                                            </ActionIcon>
                                        </Group>
                                    </Paper>
                                ))
                            )}
                        </Stack>

                        <Group align="flex-end">
                            <TextInput
                                placeholder={t('project_management.manage_paths.placeholder')}
                                value={newDirPath}
                                onChange={(e) => setNewDirPath(e.currentTarget.value)}
                                style={{ flex: 1 }}
                            />
                            <Button onClick={handleBrowseTranslationPath} leftSection={<IconFolder size={16} />}>
                                {t('project_management.manage_paths.browse')}
                            </Button>
                            <Button onClick={handleAddDir} leftSection={<IconPlus size={16} />} disabled={!newDirPath}>
                                {t('project_management.manage_paths.add')}
                            </Button>
                        </Group>
                    </div>

                    <Divider mt="xs" />

                    <Group justify="flex-end">
                        <Button variant="default" onClick={() => setManagePathsOpen(false)}>
                            {t('project_management.manage_paths.cancel')}
                        </Button>
                        <Button onClick={handleSavePaths}>
                            {t('project_management.manage_paths.save')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </>
    );
};

export default ProjectPathManager;

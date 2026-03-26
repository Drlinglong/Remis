import React, { useState, useEffect } from 'react';
import {
    Timeline, Text, Paper, Title, Group, Button,
    Stack, ActionIcon, Alert, Loader, Center,
    Divider, Code, SimpleGrid, Card
} from '@mantine/core';
import {
    IconHistory, IconGitBranch, IconTrash,
    IconCheck, IconPlayerPlay, IconInfoCircle, IconUpload
} from '@tabler/icons-react';
import api from '../../utils/api';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const ProjectHistoryComponent = ({ projectId, projectDetails, refreshToken = 0, onProjectDataChanged }) => {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);

    const fetchHistory = async () => {
        try {
            setLoading(true);
            const res = await api.get(`/api/project/${projectId}/history`);
            setHistory(res.data);
        } catch (error) {
            console.error("Failed to fetch history", error);
        } finally {
            setLoading(false);
        }
    };

    const refreshProjectData = async () => {
        if (onProjectDataChanged) {
            await onProjectDataChanged();
        }
    };

    const openIncrementalUpdate = () => {
        navigate('/incremental-translation', {
            state: {
                projectId,
            }
        });
    };

    const uploadTranslations = async () => {
        try {
            setUploading(true);
            await api.post(`/api/project/${projectId}/upload-translations`);
            await Promise.all([
                fetchHistory(),
                refreshProjectData(),
            ]);
        } catch (error) {
            console.error("Failed to upload translations", error);
        } finally {
            setUploading(false);
        }
    };

    const handleDeleteHistory = async (historyId) => {
        if (!window.confirm(t('common.confirm_delete', "Are you sure you want to delete this history record?"))) return;
        try {
            await api.delete(`/api/project/history/${historyId}`);
            setHistory(prev => prev.filter(h => h.history_id !== historyId));
        } catch (error) {
            console.error("Failed to delete history", error);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [projectId]);

    useEffect(() => {
        if (!refreshToken) return;
        fetchHistory();
    }, [refreshToken]);

    const translateHistoryAction = (actionType) => {
        const actionKey = `agent_workshop.history.action_${actionType}`;
        if (i18n.exists(actionKey)) {
            return t(actionKey);
        }
        return t(`history.action_${actionType}`, actionType.toUpperCase());
    };

    const translateHistoryDescription = (event) => {
        const metadata = event.extra_metadata || {};

        if (typeof event.description === 'string' && i18n.exists(event.description)) {
            return t(event.description, metadata);
        }

        if (typeof event.description === 'string' && event.description.startsWith('history.')) {
            const legacyKey = event.description.replace(/^history\./, 'agent_workshop.history.');
            if (i18n.exists(legacyKey)) {
                return t(legacyKey, metadata);
            }
        }

        if (event.action_type === 'archive_update') {
            if (typeof metadata.match_count === 'number') {
                return t('agent_workshop.history.archive_update_desc', metadata);
            }
            if (typeof event.description === 'string' && event.description.startsWith('Uploaded ')) {
                return t('agent_workshop.history.archive_update_desc', metadata);
            }
        }

        if (event.action_type === 'import') {
            if (typeof event.description === 'string' && event.description.startsWith("Project '")) {
                return t('agent_workshop.history.project_import_desc', { name: metadata.name || '' });
            }
        }

        if (event.action_type === 'path_registered') {
            if (
                event.description === 'history.path_registered_desc' ||
                event.description === 'Auto-registered translation output path'
            ) {
                return t('agent_workshop.history.path_registered_desc');
            }
        }

        if (event.action_type === 'translate') {
            if (
                event.description === 'history.incremental_translate_desc' ||
                (typeof event.description === 'string' && event.description.startsWith('Build incremental update ('))
            ) {
                return t('agent_workshop.history.incremental_translate_desc', metadata);
            }
        }

        return event.description;
    };

    const shouldShowHistoryMetadata = (event) => {
        if (!event.extra_metadata || Object.keys(event.extra_metadata).length === 0) {
            return false;
        }

        if (typeof event.description === 'string' && i18n.exists(event.description)) {
            return false;
        }

        if (typeof event.description === 'string' && event.description.startsWith('history.')) {
            return false;
        }

        return !['archive_update', 'import', 'path_registered', 'translate'].includes(event.action_type);
    };

    const archiveSummary = projectDetails?.archive_summary || null;
    const archivedLanguages = Array.isArray(projectDetails?.archived_languages) ? projectDetails.archived_languages : [];
    const latestArchiveTime = archiveSummary?.last_upload_at || archiveSummary?.created_at || null;

    if (loading && history.length === 0) {
        return (
            <Center h={300}>
                <Loader size="lg" variant="dots" />
            </Center>
        );
    }

    return (
        <Stack p="md" gap="xl">
            <Paper withBorder p="md" radius="md" style={{ background: 'rgba(0,0,0,0.2)', backdropFilter: 'blur(10px)' }}>
                <Group justify="space-between" mb="md">
                    <Group>
                        <IconGitBranch size={24} color="var(--mantine-color-blue-filled)" />
                        <Stack gap={0}>
                            <Title order={4}>{t('project_history.current_state', 'Current State')}</Title>
                            <Text size="xs" c="dimmed">{t('project_history.monitor_desc', 'Ready for incremental translation')}</Text>
                        </Stack>
                    </Group>
                    <Button
                        variant="light"
                        color="cyan"
                        leftSection={<IconUpload size={16} />}
                        loading={uploading}
                        onClick={uploadTranslations}
                    >
                        {t('project_management.upload_translations')}
                    </Button>
                </Group>

                <Divider mb="md" />

                <SimpleGrid cols={{ base: 1, sm: 2, lg: 5 }} mb="md">
                    <Card withBorder p="sm" radius="md">
                        <Text size="xs" c="dimmed">{t('project_history.last_archive_time', 'Last Upload / Build')}</Text>
                        <Text size="sm" fw={600}>{latestArchiveTime ? new Date(latestArchiveTime).toLocaleString() : t('project_history.no_archive_data', 'No archive data')}</Text>
                    </Card>
                    <Card withBorder p="sm" radius="md">
                        <Text size="xs" c="dimmed">{t('project_history.source_entries', 'Source Entries')}</Text>
                        <Text size="sm" fw={600}>{archiveSummary?.source_entry_count ?? 0}</Text>
                    </Card>
                    <Card withBorder p="sm" radius="md">
                        <Text size="xs" c="dimmed">{t('project_history.translation_entries', 'Translation Entries')}</Text>
                        <Text size="sm" fw={600}>{archiveSummary?.total_translation_entries ?? 0}</Text>
                    </Card>
                    <Card withBorder p="sm" radius="md">
                        <Text size="xs" c="dimmed">{t('project_history.files_count', 'Files')}</Text>
                        <Text size="sm" fw={600}>{archiveSummary?.source_file_count ?? projectDetails?.overview?.totalFiles ?? 0}</Text>
                    </Card>
                    <Card withBorder p="sm" radius="md">
                        <Text size="xs" c="dimmed">{t('project_history.target_language_count', 'Target Languages')}</Text>
                        <Text size="sm" fw={600}>{archiveSummary?.target_language_count ?? archivedLanguages.length}</Text>
                    </Card>
                </SimpleGrid>

                <Text size="xs" c="dimmed">{t('project_history.archived_languages', 'Archived Target Languages')}</Text>
                <Text size="sm" mb="md">{archivedLanguages.length > 0 ? archivedLanguages.join(', ') : t('project_history.no_archived_languages', 'No archived target languages yet.')}</Text>

                <Alert color="blue" icon={<IconInfoCircle size={16} />}>
                    <Text size="sm">{t('project_history.incremental_prompt', 'Need to update translations after getting a new mod version?')}</Text>
                    <Button
                        mt="md"
                        color="blue"
                        leftSection={<IconPlayerPlay size={16} />}
                        onClick={openIncrementalUpdate}
                    >
                        {t('project_history.btn_incremental_update', 'Open Incremental Update')}
                    </Button>
                </Alert>
            </Paper>

            <Stack gap="md">
                <Title order={4} mb="sm">
                    <Group gap="xs">
                        <IconHistory size={20} />
                        {t('project_history.title', 'Project History & Versions')}
                    </Group>
                </Title>

                <Timeline active={0} bulletSize={32} lineWidth={2}>
                    {history.length === 0 ? (
                        <Timeline.Item bullet={<IconInfoCircle size={18} />} title={t('project_history.no_history', 'No history yet')}>
                            <Text size="sm" c="dimmed">{t('project_history.no_history_desc', 'Major project events will appear here.')}</Text>
                        </Timeline.Item>
                    ) : (
                        history.map((event) => (
                            <Timeline.Item
                                key={event.history_id}
                                bullet={
                                    event.action_type === 'translate' ? <IconGitBranch size={18} /> :
                                    event.action_type === 'import' ? <IconCheck size={18} /> :
                                    <IconInfoCircle size={18} />
                                }
                                title={
                                    <Group justify="space-between">
                                        <Text fw={700}>{translateHistoryAction(event.action_type)}</Text>
                                        <Text size="xs" c="dimmed">{new Date(event.timestamp).toLocaleString()}</Text>
                                    </Group>
                                }
                            >
                                <Paper withBorder p="sm" mt="xs" radius="md">
                                    <Stack gap="xs">
                                        <Text size="sm">{translateHistoryDescription(event)}</Text>
                                        {shouldShowHistoryMetadata(event) && (
                                            <Code block style={{ background: 'rgba(0,0,0,0.1)' }}>
                                                {JSON.stringify(event.extra_metadata, null, 2)}
                                            </Code>
                                        )}
                                        <Group justify="flex-end">
                                            <ActionIcon variant="subtle" color="red" size="sm" onClick={() => handleDeleteHistory(event.history_id)}>
                                                <IconTrash size={14} />
                                            </ActionIcon>
                                        </Group>
                                    </Stack>
                                </Paper>
                            </Timeline.Item>
                        ))
                    )}
                </Timeline>
            </Stack>
        </Stack>
    );
};

export default ProjectHistoryComponent;

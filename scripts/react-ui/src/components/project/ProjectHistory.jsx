import React, { useState, useEffect } from 'react';
import {
    Timeline, Text, Paper, Title, Group, Badge, Button,
    Stack, ActionIcon, Tooltip, Alert, Loader, Center,
    Divider, Modal, Code
} from '@mantine/core';
import {
    IconHistory, IconGitBranch, IconRefresh, IconTrash,
    IconCheck, IconAlertTriangle, IconPlayerPlay, IconInfoCircle
} from '@tabler/icons-react';
import api from '../../utils/api';
import { useTranslation } from 'react-i18next';

const ProjectHistoryComponent = ({ projectId, projectDetails }) => {
    const { t } = useTranslation();
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [checkingDiff, setCheckingDiff] = useState(false);
    const [diffResult, setDiffResult] = useState(null);
    const [updating, setUpdating] = useState(false);

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

    const checkDiff = async () => {
        try {
            setCheckingDiff(true);
            setDiffResult(null);
            // Call with dry_run=true
            const res = await api.post(`/api/project/${projectId}/incremental-update?dry_run=true`);
            setDiffResult(res.data.summary);
        } catch (error) {
            console.error("Failed to check diff", error);
        } finally {
            setCheckingDiff(false);
        }
    };

    const runUpdate = async () => {
        try {
            setUpdating(true);
            const res = await api.post(`/api/project/${projectId}/incremental-update`);
            // After success, refresh history
            await fetchHistory();
            setDiffResult(null);
        } catch (error) {
            console.error("Failed to run incremental update", error);
        } finally {
            setUpdating(false);
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
        checkDiff(); // Auto check diff on mount
    }, [projectId]);

    if (loading && history.length === 0) {
        return (
            <Center h={300}>
                <Loader size="lg" variant="dots" />
            </Center>
        );
    }

    return (
        <Stack p="md" gap="xl">
            {/* Current State / Version Control Monitor */}
            <Paper withBorder p="md" radius="md" style={{ background: 'rgba(0,0,0,0.2)', backdropFilter: 'blur(10px)' }}>
                <Group justify="space-between" mb="md">
                    <Group>
                        <IconGitBranch size={24} color="var(--mantine-color-blue-filled)" />
                        <Stack gap={0}>
                            <Title order={4}>{t('project_history.current_state', 'Current State')}</Title>
                            <Text size="xs" c="dimmed">{t('project_history.monitor_desc', 'Monitoring local changes against last version')}</Text>
                        </Stack>
                    </Group>
                    <Button
                        variant="light"
                        leftSection={<IconRefresh size={16} />}
                        loading={checkingDiff}
                        onClick={checkDiff}
                    >
                        {t('button_rescan', 'Rescan')}
                    </Button>
                </Group>

                <Divider mb="md" />

                {diffResult ? (
                    <Stack>
                        {diffResult.new_lines > 0 || diffResult.changed_lines > 0 ? (
                            <Alert color="yellow" icon={<IconAlertTriangle size={16} />}>
                                <Text fw={600} size="sm">
                                    {t('project_history.changes_detected', 'Unsynchronized Changes Detected')}
                                </Text>
                                <Group gap="xl" mt="xs">
                                    <Text size="xs">🆕 {t('project_history.new_lines', 'New Lines')}: <b>{diffResult.new_lines}</b></Text>
                                    <Text size="xs">🔄 {t('project_history.changed_lines', 'Changed Lines')}: <b>{diffResult.changed_lines}</b></Text>
                                    <Text size="xs">📂 {t('project_history.files_count', 'Files')}: <b>{diffResult.files_checked}</b></Text>
                                </Group>
                                <Button
                                    mt="md"
                                    color="yellow"
                                    leftSection={<IconPlayerPlay size={16} />}
                                    loading={updating}
                                    onClick={runUpdate}
                                >
                                    {t('project_history.btn_incremental_update', 'Start Incremental Update')}
                                </Button>
                            </Alert>
                        ) : (
                            <Alert color="green" icon={<IconCheck size={16} />}>
                                <Text size="sm">{t('project_history.up_to_date', 'Everything is up to date. No changes detected since last version.')}</Text>
                            </Alert>
                        )}
                    </Stack>
                ) : !checkingDiff && (
                    <Center h={60}>
                        <Text size="sm" c="dimmed">{t('project_history.scan_prompt', 'Click Rescan to check for local modifications.')}</Text>
                    </Center>
                )}
            </Paper>

            {/* History Timeline */}
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
                        history.map((event, idx) => (
                            <Timeline.Item
                                key={event.history_id}
                                bullet={
                                    event.action_type === 'translate' ? <IconGitBranch size={18} /> :
                                        event.action_type === 'import' ? <IconCheck size={18} /> :
                                            <IconInfoCircle size={18} />
                                }
                                title={
                                    <Group justify="space-between">
                                        <Text fw={700}>{event.action_type.toUpperCase()}</Text>
                                        <Text size="xs" c="dimmed">{new Date(event.timestamp).toLocaleString()}</Text>
                                    </Group>
                                }
                            >
                                <Paper withBorder p="sm" mt="xs" radius="md">
                                    <Stack gap="xs">
                                        <Text size="sm">{event.description}</Text>
                                        {event.extra_metadata && (
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

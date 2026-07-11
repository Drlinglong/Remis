import React, { useCallback, useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Container, Grid, Paper, Title, Text, Stack, Group, Button,
    ScrollArea, Select, Checkbox, Progress, Alert
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
    IconRadar2, IconCpu, IconFileText, IconSparkles, IconInfoCircle
} from '@tabler/icons-react';
import api from '../../utils/api';

const API_BASE_URL = '/api';

const getProjectFilePath = (file) => file.file_path || file.path || '';
const getProjectFileLabel = (file) => file.relative_path || file.rel_path || file.file_path || file.path || '';

/**
 * 新词挖掘仪表板组件
 * 负责配置和启动 AI 新词扫描
 */
const MiningDashboard = ({ selectedProject, onSelectedProjectChange, onMiningComplete }) => {
    const { t } = useTranslation();
    const [projects, setProjects] = useState([]);
    const [files, setFiles] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [providers, setProviders] = useState([]);
    const [apiProvider, setApiProvider] = useState('gemini');
    const [modelName, setModelName] = useState(null);
    const [targetLang, setTargetLang] = useState('zh-CN');
    const [scanning, setScanning] = useState(false);
    const [miningStatus, setMiningStatus] = useState(null);
    const wsRef = useRef(null);
    const pollRef = useRef(null);
    const terminalHandledRef = useRef(false);

    useEffect(() => {
        const provider = providers.find((item) => item.value === apiProvider);
        setModelName(provider?.selected_model || provider?.default_model || provider?.available_models?.[0] || null);
    }, [apiProvider, providers]);

    const closeMiningSocket = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.onclose = null;
            wsRef.current.onerror = null;
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const stopPolling = useCallback(() => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, []);

    const handleTerminalStatus = useCallback((status) => {
        if (!['completed', 'failed'].includes(status) || terminalHandledRef.current) return;
        terminalHandledRef.current = true;
        stopPolling();
        closeMiningSocket();
        if (status === 'completed') onMiningComplete?.();
    }, [closeMiningSocket, onMiningComplete, stopPolling]);

    const applyProjectStatus = useCallback((status) => {
        setMiningStatus(status);
        handleTerminalStatus(status?.status);
    }, [handleTerminalStatus]);

    const startPolling = useCallback((projectId) => {
        stopPolling();
        pollRef.current = window.setInterval(async () => {
            try {
                const response = await api.get(`${API_BASE_URL}/neologisms/status/${encodeURIComponent(projectId)}`);
                applyProjectStatus(response.data);
            } catch (error) {
                console.error('Failed to poll mining status', error);
            }
        }, 1500);
    }, [applyProjectStatus, stopPolling]);

    const fetchMiningStatus = useCallback(async (projectId) => {
        try {
            const response = await api.get(`${API_BASE_URL}/neologisms/status/${encodeURIComponent(projectId)}`);
            if (response.data?.status && response.data.status !== 'idle') {
                applyProjectStatus(response.data);
                if (['starting', 'running'].includes(response.data.status)) startPolling(projectId);
            }
        } catch (error) {
            console.error('Failed to restore mining status', error);
        }
    }, [applyProjectStatus, startPolling]);

    const updateMiningStatusFromTask = (taskData) => {
        const progress = taskData.progress || {};
        const summary = taskData.summary || {};
        const status = {
            status: taskData.status === 'processing' ? 'running' : taskData.status,
            processed_files: progress.current || 0,
            total_files: progress.total || 0,
            new_terms: summary.new_terms || 0,
            duplicate_terms: summary.duplicate_terms || 0,
            current_file: progress.current_file || null,
            error: summary.error || taskData.error || null,
        };
        applyProjectStatus(status);
    };

    const connectMiningSocket = (taskId) => {
        closeMiningSocket();
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/status/${taskId}`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            const taskData = JSON.parse(event.data);
            updateMiningStatusFromTask(taskData);
        };
        ws.onerror = () => {
            setMiningStatus((current) => ({
                ...(current || {}),
                status: current?.status || 'running',
                error: t('neologism_review.mining.websocket_failed'),
            }));
            closeMiningSocket();
            startPolling(selectedProject);
        };
        ws.onclose = () => {
            if (!terminalHandledRef.current) startPolling(selectedProject);
        };
    };

    const fetchProjects = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
            setProjects(response.data.map(p => ({ value: p.project_id, label: p.name })));
            if (!selectedProject && response.data.length > 0) {
                onSelectedProjectChange(response.data[0].project_id);
            }
        } catch (error) {
            console.error("Failed to fetch projects", error);
        }
    }, [onSelectedProjectChange, selectedProject]);

    const fetchConfig = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/config`);
            const configuredProviders = response.data?.api_providers || [];
            setProviders(configuredProviders);
            if (configuredProviders.length > 0 && !configuredProviders.some((item) => item.value === apiProvider)) {
                setApiProvider(configuredProviders[0].value);
            }
        } catch (error) {
            console.error('Failed to fetch provider configuration', error);
        }
    }, [apiProvider]);

    const fetchFiles = useCallback(async (projectId) => {
        try {
            const response = await api.get(`${API_BASE_URL}/project/${encodeURIComponent(projectId)}/files`);
            setFiles(response.data);
        } catch (error) {
            console.error("Failed to fetch files", error);
        }
    }, []);

    useEffect(() => {
        fetchProjects();
        fetchConfig();
    }, [fetchConfig, fetchProjects]);

    useEffect(() => {
        if (selectedProject) {
            terminalHandledRef.current = false;
            setMiningStatus(null);
            setSelectedFiles([]);
            fetchFiles(selectedProject);
            closeMiningSocket();
            stopPolling();
            fetchMiningStatus(selectedProject);
        } else {
            setFiles([]);
            setSelectedFiles([]);
            setMiningStatus(null);
            closeMiningSocket();
            stopPolling();
        }
    }, [closeMiningSocket, fetchFiles, fetchMiningStatus, selectedProject, stopPolling]);

    useEffect(() => () => {
        closeMiningSocket();
        stopPolling();
    }, [closeMiningSocket, stopPolling]);

    const handleScan = async () => {
        if (!selectedProject) return;
        setScanning(true);
        terminalHandledRef.current = false;
        stopPolling();
        try {
            const response = await api.post(`${API_BASE_URL}/neologisms/mine`, {
                project_id: selectedProject,
                api_provider: apiProvider,
                model_name: modelName,
                target_lang: targetLang,
                file_paths: selectedFiles.length > 0 ? selectedFiles : null
            });
            setMiningStatus({
                status: 'running',
                processed_files: 0,
                total_files: selectedFiles.length || files.length,
                new_terms: 0,
                current_file: null,
                error: null,
            });
            if (response.data?.task_id) {
                connectMiningSocket(response.data.task_id);
            }
            notifications.show({
                title: t('neologism_review.mining.start_mining'),
                message: t('neologism_review.mining.started_message'),
                color: 'blue',
                icon: <IconSparkles size={18} />
            });
        } catch {
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.mining.start_failed'),
                color: 'red'
            });
        } finally {
            setScanning(false);
        }
    };

    return (
        <Container size="lg" py="xl">
            <Title order={2} mb="xl" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <IconCpu size={32} color="var(--mantine-color-blue-4)" />
                {t('neologism_review.tab_mining')}
            </Title>

            <Grid>
                <Grid.Col span={4}>
                    <Stack>
                        <Select
                            label={t('neologism_review.mining.select_project')}
                            placeholder={t('neologism_review.mining.select_project_placeholder')}
                            data={projects}
                            value={selectedProject}
                            onChange={onSelectedProjectChange}
                            size="md"
                        />

                        <Select
                            label={t('neologism_review.mining.target_language')}
                            description={t('neologism_review.mining.target_language_desc')}
                            data={[
                                { value: 'zh-CN', label: 'Simplified Chinese (简体中文)' },
                                { value: 'zh-TW', label: 'Traditional Chinese (繁體中文)' },
                                { value: 'en', label: 'English' },
                                { value: 'ja', label: 'Japanese (日本語)' },
                                { value: 'ko', label: 'Korean (한국어)' },
                                { value: 'fr', label: 'French (Français)' },
                                { value: 'de', label: 'German (Deutsch)' },
                                { value: 'ru', label: 'Russian (Русский)' },
                                { value: 'es', label: 'Spanish (Español)' },
                                { value: 'pt', label: 'Portuguese (Português)' },
                                { value: 'pl', label: 'Polish (Polski)' }
                            ]}
                            value={targetLang}
                            onChange={setTargetLang}
                            size="md"
                        />

                        <Select
                            label={t('neologism_review.mining.select_provider')}
                            data={providers}
                            value={apiProvider}
                            onChange={setApiProvider}
                            size="md"
                        />

                        {providers.find((item) => item.value === apiProvider)?.available_models?.length > 0 && (
                            <Select
                                label={t('form_label_model')}
                                data={providers.find((item) => item.value === apiProvider).available_models}
                                value={modelName}
                                onChange={setModelName}
                                searchable
                                size="md"
                            />
                        )}

                        <Button
                            size="xl"
                            mt="xl"
                            leftSection={<IconRadar2 />}
                            onClick={handleScan}
                            loading={scanning}
                            disabled={!selectedProject || ['starting', 'running'].includes(miningStatus?.status)}
                            variant="gradient"
                            gradient={{ from: 'blue', to: 'cyan', deg: 90 }}
                        >
                            {t('neologism_review.mining.start_mining')}
                        </Button>
                        <Text size="xs" c="dimmed" ta="center">
                            {t('neologism_review.mining.mining_disclaimer')}
                        </Text>
                        {miningStatus && miningStatus.status !== 'idle' && (
                            <Alert icon={<IconInfoCircle size={16} />} color={miningStatus.status === 'failed' ? 'red' : 'blue'} variant="light">
                                <Stack gap={6}>
                                    <Group justify="space-between">
                                        <Text size="sm" fw={600}>
                                            {t(`neologism_review.mining.status_${miningStatus.status}`, miningStatus.status)}
                                        </Text>
                                        <Text size="xs" c="dimmed">
                                            {(miningStatus.processed_files || 0)} / {(miningStatus.total_files || 0)}
                                        </Text>
                                    </Group>
                                    <Progress
                                        value={miningStatus.total_files ? ((miningStatus.processed_files || 0) / miningStatus.total_files) * 100 : 0}
                                        size="sm"
                                    />
                                    {miningStatus.status === 'completed' && (
                                        <Text size="xs">
                                            {t('neologism_review.mining.completed_terms', { count: miningStatus.new_terms || 0 })}
                                            {(miningStatus.duplicate_terms || 0) > 0 && ` ${t('neologism_review.mining.duplicate_terms', { count: miningStatus.duplicate_terms })}`}
                                        </Text>
                                    )}
                                    {miningStatus.error && <Text size="xs" c="red">{miningStatus.error}</Text>}
                                </Stack>
                            </Alert>
                        )}
                    </Stack>
                </Grid.Col>

                <Grid.Col span={8}>
                    <Paper p="md" withBorder h={500} style={{ display: 'flex', flexDirection: 'column' }}>
                        <Text fw={700} mb="sm">{t('neologism_review.mining.select_files')}</Text>
                        <Text size="xs" c="dimmed" mb="md">{t('neologism_review.mining.select_files_desc')}</Text>

                        <ScrollArea style={{ flex: 1 }}>
                            {files.length > 0 ? (
                                <Checkbox.Group value={selectedFiles} onChange={setSelectedFiles}>
                                    <Stack gap="xs">
                                        {files.filter(getProjectFilePath).map(f => {
                                            const filePath = getProjectFilePath(f);
                                            const fileLabel = getProjectFileLabel(f);
                                            return (
                                            <Checkbox
                                                key={filePath}
                                                value={filePath}
                                                label={
                                                    <Group gap="xs">
                                                        <IconFileText size={14} />
                                                        <Text size="sm">{fileLabel}</Text>
                                                    </Group>
                                                }
                                            />
                                        );
                                        })}
                                    </Stack>
                                </Checkbox.Group>
                            ) : (
                                <Text c="dimmed" fs="italic">{t('neologism_review.mining.no_files')}</Text>
                            )}
                        </ScrollArea>
                    </Paper>
                </Grid.Col>
            </Grid>
        </Container>
    );
};

export default MiningDashboard;

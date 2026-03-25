import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Container,
    Stepper,
    Button,
    Group,
    Paper,
    Text,
    Title,
    Stack,
    Card,
    SimpleGrid,
    Badge,
    Alert,
    Select,
    TextInput,
    Progress,
    ScrollArea,
    Divider,
    MultiSelect,
    Box,
    LoadingOverlay,
} from '@mantine/core';
import { IconRocket, IconCheck, IconAlertCircle, IconSearch, IconFolderOpen, IconPlayerPlay, IconChartBar, IconSettings, IconCloudDownload } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { open } from '@tauri-apps/plugin-dialog';
import { useNotification } from '../context/NotificationContext';
import notificationService from '../services/notificationService';
import styles from './Translation.module.css';

const IncrementalTranslationPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { notificationStyle } = useNotification();
    const [active, setActive] = useState(0);
    const [loading, setLoading] = useState(false);

    // Data State
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);
    const [apiProviders, setApiProviders] = useState([]);
    const [selectedProvider, setSelectedProvider] = useState('gemini');
    const [selectedModel, setSelectedModel] = useState('');
    const [models, setModels] = useState([]);
    const [customSourcePath, setCustomSourcePath] = useState('');
    const [selectedLangs, setSelectedLangs] = useState([]);

    // Validation / Scan Results
    const [archiveInfo, setArchiveInfo] = useState(null);
    const [scanResults, setScanResults] = useState(null);
    const [error, setError] = useState(null);

    // Execution State
    const [executing, setExecuting] = useState(false);
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState([]);
    const [finalSummary, setFinalSummary] = useState(null);
    const logScrollRef = useRef(null);
    const [checkpointFound, setCheckpointFound] = useState(false);
    const [useResume, setUseResume] = useState(true);
    const wsRef = useRef(null);

    // Fetch basics
    useEffect(() => {
        fetchProjects();
        fetchApiConfig();
    }, []);

    const fetchProjects = async () => {
        try {
            const response = await axios.get('/api/projects');
            setProjects(response.data.filter(p => p.status === 'active'));
        } catch (err) {
            notificationService.error(t('notification.error_generic'), notificationStyle);
        }
    };

    const fetchApiConfig = async () => {
        try {
            const response = await axios.get('/api/config');
            const data = response.data;
            const providers = data.api_providers || [];

            setApiProviders(providers);

            const defaultProvider = data.default_provider || 'gemini';
            setSelectedProvider(defaultProvider);

            // Find models for default provider
            const providerData = providers.find(p => p.value === defaultProvider);
            if (providerData) {
                const availableModels = providerData.available_models || providerData.custom_models || [];
                setModels(availableModels);
                setSelectedModel(data.default_model || availableModels[0] || '');
            }
        } catch (err) {
            console.error('Failed to fetch API config', err);
        }
    };

    const handleProviderChange = (val) => {
        setSelectedProvider(val);
        const providerData = apiProviders.find(p => p.value === val);
        if (providerData) {
            const availableModels = providerData.available_models || providerData.custom_models || [];
            setModels(availableModels);
            setSelectedModel(availableModels[0] || '');
        }
    };

    const handleSelectProject = async (project) => {
        setSelectedProject(project);
        setCustomSourcePath(project.source_path);
        setError(null);
        setArchiveInfo(null);
        setCheckpointFound(false);
        setActive(1);

        // Immediate archive check
        try {
            setLoading(true);
            const res = await axios.get(`/api/project/${project.project_id}/check-archive`);
            if (res.data.exists) {
                setArchiveInfo(res.data);
                // Pre-select all available languages from archive or fallback to project target
                const availableLangs = res.data.target_languages || [res.data.target_language] || [project.target_language_code] || ['zh-CN'];
                setSelectedLangs(availableLangs);
                // Also check for checkpoint (resume status)
                checkCheckpoint(project, project.source_path, availableLangs);
            } else {
                setError(res.data.reason || t('incremental_translation.archive_missing'));
            }
        } catch (err) {
            setError(t('incremental_translation.archive_missing'));
        } finally {
            setLoading(false);
        }
    };

    const checkCheckpoint = async (project, sourcePath, targetLangs) => {
        try {
            // Determine mod_name for checkpoint lookup
            const modName = sourcePath.split(/[\\/]/).pop();
            const res = await axios.post('/api/translation/checkpoint-status', {
                project_id: project.project_id,
                mod_name: modName,
                target_lang_codes: targetLangs || [project.target_language_code || 'zh-CN']
            });
            if (res.data.exists && res.data.completed_count > 0) {
                setCheckpointFound(true);
                notificationService.info(t('incremental_translation.checkpoint_detected', { count: res.data.completed_count }), notificationStyle);
            }
        } catch (err) {
            console.error('Failed to check checkpoint status', err);
        }
    };

    const handleSelectFolder = async () => {
        try {
            const selected = await open({
                directory: true,
                multiple: false,
                title: t('incremental_translation.select_new_folder')
            });
            if (selected && typeof selected === 'string') {
                setCustomSourcePath(selected);
                // Re-check checkpoint for the new folder if project is selected
                if (selectedProject) {
                    checkCheckpoint(selectedProject, selected, selectedLangs);
                }
            }
        } catch (err) {
            console.error('Failed to open folder dialog:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
        }
    };

    const runPreScan = async () => {
        if (!selectedProject || !customSourcePath) return;

        try {
            setLoading(true);
            const res = await axios.post(`/api/project/${selectedProject.project_id}/incremental-update`, {
                project_id: selectedProject.project_id,
                target_lang_codes: selectedLangs.length > 0 ? selectedLangs : [archiveInfo?.target_language || selectedProject.target_language_code || 'zh-CN'],
                dry_run: true,
                api_provider: selectedProvider,
                model: selectedModel,
                custom_source_path: customSourcePath,
                use_resume: useResume
            });

            const taskId = res.data.task_id;
            if (taskId) {
                // Connect to WebSocket and wait for the summary
                connectWebSocket(taskId, true); // true indicates pre-scan mode
            } else {
                // Fallback for immediate response (though backend is currently async)
                if (res.data.status === 'warning') {
                    notificationService.info(res.data.message || t('incremental_translation.no_files_warning'), notificationStyle);
                }
                setScanResults(res.data.summary);
                setActive(2);
                setLoading(false);
            }
        } catch (err) {
            console.error('Pre-scan error:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
            setLoading(false);
        }
    };

    const startTranslation = async () => {
        setExecuting(true);
        setActive(3);
        setLogs([`[${new Date().toLocaleTimeString()}] Initializing WebSocket connection...`]);
        setFinalSummary(null);
        setProgress(0);

        try {
            // 1. Kick off the translation request
            const res = await axios.post(`/api/project/${selectedProject.project_id}/incremental-update`, {
                project_id: selectedProject.project_id,
                target_lang_codes: selectedLangs.length > 0 ? selectedLangs : [archiveInfo?.target_language || selectedProject.target_language_code || 'zh-CN'],
                dry_run: false,
                api_provider: selectedProvider,
                model: selectedModel,
                custom_source_path: customSourcePath,
                use_resume: useResume
            });

            const taskId = res.data.task_id;
            if (!taskId) {
                throw new Error("No Task ID returned from server.");
            }

            // 2. Connect to WebSocket for real-time updates
            connectWebSocket(taskId);

        } catch (err) {
            addLog(`Critical Error: ${err.message}`, 'error');
            setExecuting(false);
        }
    };

    const connectWebSocket = (taskId, isPreScan = false) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/api/ws/status/${taskId}`;

        console.log(`Connecting to WS (${isPreScan ? 'Pre-scan' : 'Execution'}): ${wsUrl}`);
        if (wsRef.current) wsRef.current.close();
        
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // Update progress
            if (data.progress) {
                setProgress(data.progress.percent || 0);
            }

            // Sync logs - backend sends the full tail (last 100 lines)
            if (data.log) {
                setLogs(data.log);
            }

            // Handle completion
            if (data.status === 'completed') {
                if (isPreScan) {
                    setScanResults(data.summary);
                    setActive(2);
                    setLoading(false);
                } else {
                    setFinalSummary(data);
                    addLog(`Translation completed successfully!`);
                    setProgress(100);
                    setExecuting(false);
                }
                ws.close();
            } else if (data.status === 'failed') {
                addLog(`Task failed! Check logs for details.`, 'error');
                if (isPreScan) setLoading(false);
                else setExecuting(false);
                ws.close();
            }
        };

        ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
            addLog('WebSocket connection error.', 'error');
            if (isPreScan) setLoading(false);
            else setExecuting(false);
        };

        ws.onclose = () => {
            console.log('WebSocket connection closed.');
        };
    };

    // Clean up WS on unmount
    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    const addLog = (msg, type = 'info') => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    };

    useEffect(() => {
        if (logScrollRef.current) {
            logScrollRef.current.scrollTo({ top: logScrollRef.current.scrollHeight, behavior: 'smooth' });
        }
    }, [logs]);

    const nextStep = () => setActive((current) => (current < 3 ? current + 1 : current));
    const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current));

    return (
        <Container size="xl" py="xl">
            <Title order={2} mb="xl" className={styles.pageTitle}>
                <IconRocket size={32} style={{ marginRight: 12, verticalAlign: 'middle' }} />
                {t('incremental_translation.title')}
            </Title>

            <Stepper active={active} onStepClick={setActive} allowNextStepsSelect={false} breakpoint="sm">
                {/* --- Step 1: Select Project --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_1_title')}
                    description={t('incremental_translation.step_1_desc')}
                    icon={<IconSearch size={18} />}
                >
                    <Stack mt="xl">
                        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
                            {projects.map((p) => (
                                <Card
                                    key={p.project_id}
                                    padding="lg"
                                    radius="md"
                                    withBorder
                                    onClick={() => handleSelectProject(p)}
                                    style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                                    className={selectedProject?.project_id === p.project_id ? styles.selectedCard : styles.glassCard}
                                >
                                    <Title order={5}>{p.name}</Title>
                                    <Text size="xs" c="dimmed" mb="sm">{p.game_id}</Text>
                                    <Badge color="blue" variant="light">{p.source_language}</Badge>
                                </Card>
                            ))}
                        </SimpleGrid>
                    </Stack>
                </Stepper.Step>

                {/* --- Step 2: Validation & Setup --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_2_title')}
                    description={t('incremental_translation.step_2_desc')}
                    icon={<IconSettings size={18} />}
                >
                    <Stack mt="xl" gap="md" style={{ position: 'relative' }}>
                        <LoadingOverlay visible={loading} overlayProps={{ radius: "sm", blur: 2 }} />
                        
                        {loading && (
                            <Paper withBorder p="md" radius="md">
                                <Stack gap="xs">
                                    <Text size="sm" fw={500}>{t('incremental_translation.status_processing')}</Text>
                                    <Progress value={progress} animated />
                                    <Text size="xs" c="dimmed">{logs[logs.length - 1]}</Text>
                                </Stack>
                            </Paper>
                        )}

                        {error && (
                            <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red" radius="md">
                                {error}
                                <Box mt="sm">
                                    <Text size="sm">{t('incremental_translation.archive_missing_action')}</Text>
                                </Box>
                                <Button variant="outline" color="red" size="xs" mt="md" onClick={() => setActive(0)}>
                                    {t('common.back')}
                                </Button>
                            </Alert>
                        )}

                        {archiveInfo && (
                            <Paper withBorder p="lg" radius="md" className={styles.glassCard}>
                                <Stack>
                                    <Group justify="space-between">
                                        <Title order={4}>
                                            {t('incremental_translation.step_2_title')} - {archiveInfo.project_name || selectedProject?.name}
                                        </Title>
                                        <Group gap="xs">
                                            {checkpointFound && (
                                                <Badge color="orange" variant="filled">
                                                    {t('incremental_translation.checkpoint_found_label')}
                                                </Badge>
                                            )}
                                            <Badge color="green" leftSection={<IconCheck size={12} />}>
                                                {t('incremental_translation.archive_found', {
                                                    version: archiveInfo.version_id.substring(0, 8),
                                                    date: new Date(archiveInfo.created_at).toLocaleDateString()
                                                })}
                                            </Badge>
                                        </Group>
                                    </Group>

                                    <Divider />

                                    {checkpointFound && (
                                        <Alert icon={<IconSettings size={16} />} title={t('incremental_translation.checkpoint_found_title')} color="orange" radius="md">
                                            <Group justify="space-between">
                                                <Text size="sm">{t('incremental_translation.checkpoint_found_desc')}</Text>
                                                <Button
                                                    size="xs"
                                                    variant={useResume ? "filled" : "outline"}
                                                    color="orange"
                                                    onClick={() => setUseResume(!useResume)}
                                                >
                                                    {useResume ? t('incremental_translation.resume_enabled') : t('incremental_translation.resume_disabled')}
                                                </Button>
                                            </Group>
                                        </Alert>
                                    )}

                                    <MultiSelect
                                        label={t('translation_config.target_languages') || "Target Languages"}
                                        description="Languages to process based on archive data"
                                        data={(archiveInfo.target_languages || [archiveInfo.target_language || selectedProject?.target_language_code || 'zh-CN']).map(lang => ({ value: lang, label: lang }))}
                                        value={selectedLangs}
                                        onChange={setSelectedLangs}
                                        required
                                        clearable
                                    />

                                    <SimpleGrid cols={2}>
                                        <Select
                                            label={t('translation_config.provider')}
                                            data={apiProviders.map(p => ({ value: p.value, label: p.label }))}
                                            value={selectedProvider}
                                            onChange={handleProviderChange}
                                        />
                                        <Select
                                            label={t('translation_config.model')}
                                            data={models.map(m => ({ value: m, label: m }))}
                                            value={selectedModel}
                                            onChange={setSelectedModel}
                                        />
                                    </SimpleGrid>

                                    <Box>
                                        <Text size="sm" fw={500} mb={4}>{t('incremental_translation.select_new_folder')}</Text>
                                        <Group gap="xs">
                                            <TextInput
                                                style={{ flex: 1 }}
                                                value={customSourcePath}
                                                readOnly
                                            />
                                            <Button variant="light" leftSection={<IconFolderOpen size={16} />} onClick={handleSelectFolder}>
                                                {t('common.browse')}
                                            </Button>
                                        </Group>
                                        <Text size="xs" c="dimmed" mt={4}>
                                            {t('incremental_translation.current_folder_info', { path: selectedProject?.source_path })}
                                        </Text>
                                    </Box>

                                    <Group justify="flex-end" mt="md">
                                        <Button variant="light" onClick={prevStep}>{t('common.back')}</Button>
                                        <Button onClick={runPreScan}>{t('incremental_translation.step_3_title')}</Button>
                                    </Group>
                                </Stack>
                            </Paper>
                        )}
                    </Stack>
                </Stepper.Step>

                {/* --- Step 3: Pre-scan Results --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_3_title')}
                    description={t('incremental_translation.step_3_desc')}
                    icon={<IconChartBar size={18} />}
                >
                    <Stack mt="xl">
                        {scanResults && (
                            <Paper withBorder p="xl" radius="md" className={styles.glassCard}>
                                <Title order={4} mb="md">{t('incremental_translation.pre_scan_summary')}</Title>
                                <SimpleGrid cols={2} mb="lg">
                                    <Box>
                                        <Text size="xs" c="dimmed">{t('incremental_translation.scan_directory')}</Text>
                                        <Text size="sm" truncate>{customSourcePath}</Text>
                                    </Box>
                                    <Box>
                                        <Text size="xs" c="dimmed">{t('incremental_translation.source_language')}</Text>
                                        <Text size="sm">{selectedProject?.source_language}</Text>
                                    </Box>
                                </SimpleGrid>

                                <Divider mb="lg" />

                                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="xl">
                                    <Card withBorder p="md" radius="md">
                                        <Text size="xs" c="dimmed" mb={4}>{t('summary_total')}</Text>
                                        <Title order={3}>{scanResults.total}</Title>
                                    </Card>
                                    <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-green-6)' }}>
                                        <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.reused_count', { count: '' })}</Text>
                                        <Title order={3} c="green">{scanResults.unchanged}</Title>
                                    </Card>
                                    <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-orange-6)' }}>
                                        <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.new_count', { count: '' })}</Text>
                                        <Title order={3} c="orange">{scanResults.new + scanResults.changed}</Title>
                                    </Card>
                                </SimpleGrid>

                                <Alert icon={<IconAlertCircle size={16} />} color="blue">
                                    {t('incremental_translation.start_translation_confirm')}
                                </Alert>

                                <Group justify="flex-end" mt="xl">
                                    <Button variant="light" onClick={prevStep}>{t('common.back')}</Button>
                                    <Button size="lg" leftSection={<IconPlayerPlay size={20} />} onClick={startTranslation}>
                                        {t('incremental_translation.step_4_title')}
                                    </Button>
                                </Group>
                            </Paper>
                        )}
                    </Stack>
                </Stepper.Step>

                {/* --- Step 4: Execution --- */}
                <Stepper.Completed>
                    <Stack mt="xl">
                        <Paper withBorder p="xl" radius="md" className={styles.glassCard}>
                            <Title order={4} mb="md">{t('incremental_translation.execution_log')}</Title>

                            <Progress
                                value={progress}
                                label={progress > 0 ? `${progress}%` : ''}
                                size="xl"
                                radius="xl"
                                animated={executing}
                                mb="sm"
                            />

                            <Group justify="space-between" mb="xl">
                                <Text size="xs" c="dimmed">
                                    {executing ? t('incremental_translation.status_processing') : t('incremental_translation.status_idle')}
                                </Text>
                                <Text size="xs" fw={700} c="blue">
                                    {progress}%
                                </Text>
                            </Group>

                            <ScrollArea h={400} offsetScrollbars p="md" style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: '1px solid var(--glass-border)' }}>
                                <div ref={logScrollRef}>
                                    {logs.map((log, i) => {
                                        const isError = log.includes('ERROR') || log.includes('failed');
                                        return (
                                            <Text key={i} size="xs" style={{ fontFamily: 'monospace', color: isError ? '#ff6b6b' : 'inherit' }} mb={2}>
                                                {log}
                                            </Text>
                                        );
                                    })}
                                </div>
                            </ScrollArea>

                            {finalSummary && (
                                <Stack mt="xl">
                                    <Title order={4} c="green">{t('incremental_translation.completion_title')}</Title>
                                    <Alert color="green">
                                        {t('incremental_translation.output_dir_hint')}
                                    </Alert>
                                    <Button size="lg" onClick={() => navigate('/project-management')}>
                                        {t('common.finish')}
                                    </Button>
                                </Stack>
                            )}
                        </Paper>
                    </Stack>
                </Stepper.Completed>
            </Stepper>
        </Container>
    );
};

export default IncrementalTranslationPage;

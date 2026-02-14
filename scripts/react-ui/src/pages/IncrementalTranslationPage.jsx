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
    Box,
    Progress,
    ScrollArea,
    Table,
    Divider,
} from '@mantine/core';
import {
    IconRocket,
    IconCheck,
    IconAlertCircle,
    IconSearch,
    IconFolderOpen,
    IconPlayerPlay,
    IconChartBar,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { notificationManager } from '../context/NotificationContext';
import styles from './Translation.module.css';

const IncrementalTranslationPage = () => {
    const { t } = useTranslation();
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
            notificationManager.error(t('notification.error_generic'));
        }
    };

    const fetchApiConfig = async () => {
        try {
            const [providersRes, configRes] = await Promise.all([
                axios.get('/api/config/api-providers'),
                axios.get('/api/config')
            ]);

            const providers = providersRes.data;
            setApiProviders(providers);

            const defaultProvider = configRes.data.default_provider || 'gemini';
            setSelectedProvider(defaultProvider);

            // Find models for default provider
            const providerData = providers.find(p => p.id === defaultProvider);
            if (providerData) {
                const availableModels = providerData.available_models || providerData.custom_models || [];
                setModels(availableModels);
                setSelectedModel(configRes.data.default_model || availableModels[0] || '');
            }
        } catch (err) {
            console.error('Failed to fetch API config', err);
        }
    };

    const handleProviderChange = (val) => {
        setSelectedProvider(val);
        const providerData = apiProviders.find(p => p.id === val);
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
        setActive(1);

        // Immediate archive check
        try {
            setLoading(true);
            const res = await axios.get(`/api/project/${project.project_id}/check-archive`);
            if (res.data.exists) {
                setArchiveInfo(res.data);
            } else {
                setError(res.data.reason || t('incremental_translation.archive_missing'));
            }
        } catch (err) {
            setError(t('incremental_translation.archive_missing'));
        } finally {
            setLoading(false);
        }
    };

    const handleSelectFolder = async () => {
        if (window.api && window.api.selectFolder) {
            const path = await window.api.selectFolder();
            if (path) {
                setCustomSourcePath(path);
            }
        }
    };

    const runPreScan = async () => {
        if (!selectedProject || !customSourcePath) return;

        try {
            setLoading(true);
            const res = await axios.post(`/api/project/${selectedProject.project_id}/incremental-update`, {
                dry_run: true,
                provider: selectedProvider,
                model: selectedModel,
                custom_source_path: customSourcePath
            });
            setScanResults(res.data.summary);
            setActive(2);
        } catch (err) {
            notificationManager.error(t('notification.error_generic'));
        } finally {
            setLoading(false);
        }
    };

    const startTranslation = async () => {
        setExecuting(true);
        setActive(3);
        setLogs([`[${new Date().toLocaleTimeString()}] Starting incremental translation...`]);
        setFinalSummary(null);
        setProgress(5);

        try {
            const res = await axios.post(`/api/project/${selectedProject.project_id}/incremental-update`, {
                dry_run: false,
                provider: selectedProvider,
                model: selectedModel,
                custom_source_path: customSourcePath
            });

            if (res.data.status === 'success') {
                setFinalSummary(res.data);
                addLog(`Translation completed successfully!`);
                setProgress(100);
            } else {
                addLog(`Error: ${res.data.message}`, 'error');
            }
        } catch (err) {
            addLog(`Critical Error: ${err.message}`, 'error');
        } finally {
            setExecuting(false);
        }
    };

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
                    <Stack mt="xl" gap="md">
                        {loading && <Text>Loading...</Text>}

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
                                        <Title order={4}>{t('incremental_translation.step_2_title')}</Title>
                                        <Badge color="green" leftSection={<IconCheck size={12} />}>
                                            {t('incremental_translation.archive_found', {
                                                version: archiveInfo.version_id.substring(0, 8),
                                                date: new Date(archiveInfo.created_at).toLocaleDateString()
                                            })}
                                        </Badge>
                                    </Group>

                                    <Divider />

                                    <SimpleGrid cols={2}>
                                        <Select
                                            label={t('translation_config.provider')}
                                            data={apiProviders.map(p => ({ value: p.id, label: p.name }))}
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
                                label={progress > 10 ? `${progress}%` : ''}
                                size="xl"
                                radius="xl"
                                animated={executing}
                                mb="xl"
                            />

                            <ScrollArea h={300} offsetScrollbars p="md" style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8 }}>
                                <div ref={logScrollRef}>
                                    {logs.map((log, i) => (
                                        <Text key={i} size="xs" style={{ fontFamily: 'monospace' }} mb={2}>
                                            {log}
                                        </Text>
                                    ))}
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

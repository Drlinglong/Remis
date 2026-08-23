import React, { useCallback, useState, useEffect, useMemo } from 'react';
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
import { normalizeArrayPayload } from '../../utils/payload';
import { useNeologismMiningTaskMonitor } from '../../hooks/useNeologismMiningTaskMonitor';

const API_BASE_URL = '/api';

const getProjectFilePath = (file) => file.file_path || file.path || '';
const getProjectFileLabel = (file) => file.relative_path || file.rel_path || file.file_path || file.path || '';
const TARGET_LANGUAGE_OPTIONS = [
    { value: 'zh-CN', label: 'Simplified Chinese (简体中文)' },
    { value: 'zh-TW', label: 'Traditional Chinese (繁體中文)' },
    { value: 'en', label: 'English' },
    { value: 'ja', label: 'Japanese (日本語)' },
    { value: 'ko', label: 'Korean (한국어)' },
    { value: 'fr', label: 'French (Français)' },
    { value: 'de', label: 'German (Deutsch)' },
    { value: 'ru', label: 'Russian (Русский)' },
    { value: 'es', label: 'Spanish (Español)' },
    { value: 'pt-BR', label: 'Portuguese (Português)' },
    { value: 'pl', label: 'Polish (Polski)' },
    { value: 'tr', label: 'Turkish (Türkçe)' }
];
const LANGUAGE_ALIASES = {
    english: 'en',
    l_english: 'en',
    chinese: 'zh-CN',
    simp_chinese: 'zh-CN',
    l_simp_chinese: 'zh-CN',
    zh: 'zh-CN',
    'zh-cn': 'zh-CN',
    'zh_cn': 'zh-CN',
    pt: 'pt-BR',
    'pt-br': 'pt-BR',
    pt_br: 'pt-BR',
};
const normalizeLanguageCode = (value) => {
    const normalized = (value || '').trim().toLowerCase();
    return LANGUAGE_ALIASES[normalized] || normalized;
};

/**
 * 新词挖掘仪表板组件
 * 负责配置和启动 AI 新词扫描
 */
const MiningDashboard = ({ selectedProject, onSelectedProjectChange, onMiningComplete }) => {
    const { t, i18n } = useTranslation();
    const interfaceLanguage = normalizeLanguageCode(
        i18n?.resolvedLanguage || i18n?.language || 'en',
    );
    const [projects, setProjects] = useState([]);
    const [files, setFiles] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [providers, setProviders] = useState([]);
    const [apiProvider, setApiProvider] = useState('gemini');
    const [modelName, setModelName] = useState(null);
    const [targetLang, setTargetLang] = useState('zh-CN');
    const [reviewLanguage, setReviewLanguage] = useState(interfaceLanguage);
    const [scanning, setScanning] = useState(false);
    const [miningStatus, setMiningStatus] = useState(null);

    useEffect(() => {
        const provider = providers.find((item) => item.value === apiProvider);
        setModelName(provider?.selected_model || provider?.default_model || provider?.available_models?.[0] || null);
    }, [apiProvider, providers]);

    useEffect(() => {
        setReviewLanguage(interfaceLanguage);
    }, [interfaceLanguage]);

    const handleMiningTerminal = useCallback((status) => {
        if (status.status === 'completed') onMiningComplete?.();
    }, [onMiningComplete]);

    const handleWebSocketError = useCallback(() => {
        setMiningStatus((current) => ({
            ...(current || {}),
            status: current?.status || 'running',
            error: t('neologism_review.mining.websocket_failed'),
        }));
    }, [t]);

    const { startMiningTask } = useNeologismMiningTaskMonitor({
        projectId: selectedProject,
        onStatus: setMiningStatus,
        onTerminal: handleMiningTerminal,
        onWebSocketError: handleWebSocketError,
    });

    const fetchProjects = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
            const projectList = normalizeArrayPayload(response.data, ['projects', 'items', 'data', 'results']);
            setProjects(projectList.map(p => ({
                value: p.project_id,
                label: p.name,
                sourceLanguage: normalizeLanguageCode(p.source_language || 'en'),
            })));
            if (!selectedProject && projectList.length > 0) {
                onSelectedProjectChange(projectList[0].project_id);
            }
        } catch (error) {
            console.error("Failed to fetch projects", error);
        }
    }, [onSelectedProjectChange, selectedProject]);

    const fetchConfig = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/config`);
            const configuredProviders = normalizeArrayPayload(
                response.data,
                ['api_providers', 'providers', 'items', 'data', 'results'],
            );
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
            const response = await api.get(`${API_BASE_URL}/neologisms/mining-files/${encodeURIComponent(projectId)}`);
            setFiles(normalizeArrayPayload(response.data, ['files', 'items', 'data', 'results']));
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
            setMiningStatus(null);
            setSelectedFiles([]);
            fetchFiles(selectedProject);
        } else {
            setFiles([]);
            setSelectedFiles([]);
            setMiningStatus(null);
        }
    }, [fetchFiles, selectedProject]);

    const currentProject = projects.find((project) => project.value === selectedProject);
    const availableTargetLanguages = useMemo(
        () => TARGET_LANGUAGE_OPTIONS.filter(
            (language) => normalizeLanguageCode(language.value) !== currentProject?.sourceLanguage
        ),
        [currentProject?.sourceLanguage],
    );

    useEffect(() => {
        if (
            availableTargetLanguages.length > 0
            && !availableTargetLanguages.some((language) => language.value === targetLang)
        ) {
            setTargetLang(availableTargetLanguages[0].value);
        }
    }, [availableTargetLanguages, targetLang]);

    const handleScan = async () => {
        if (
            !selectedProject
            || !targetLang
            || normalizeLanguageCode(targetLang) === currentProject?.sourceLanguage
        ) return;
        setScanning(true);
        try {
            const response = await api.post(`${API_BASE_URL}/neologisms/mine`, {
                project_id: selectedProject,
                api_provider: apiProvider,
                model_name: modelName,
                target_lang: targetLang,
                review_language: reviewLanguage,
                file_paths: selectedFiles.length > 0 ? selectedFiles : null
            });
            setMiningStatus({
                status: 'running',
                processed_files: 0,
                total_files: response.data?.total_files || selectedFiles.length || files.length,
                new_terms: 0,
                current_file: null,
                error: null,
            });
            startMiningTask(response.data?.task_id || null);
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
                            data={availableTargetLanguages}
                            value={targetLang}
                            onChange={setTargetLang}
                            size="md"
                        />

                        <Select
                            label={t('neologism_review.mining.review_language')}
                            description={t('neologism_review.mining.review_language_desc')}
                            data={TARGET_LANGUAGE_OPTIONS}
                            value={reviewLanguage}
                            onChange={setReviewLanguage}
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
                            label={t('neologism_review.mining.model')}
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
                            disabled={
                                !selectedProject
                                || !targetLang
                                || normalizeLanguageCode(targetLang) === currentProject?.sourceLanguage
                                || ['pending', 'starting', 'running'].includes(miningStatus?.status)
                            }
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

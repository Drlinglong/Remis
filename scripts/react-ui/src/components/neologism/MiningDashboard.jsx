import React, { useState, useEffect } from 'react';
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
const MiningDashboard = () => {
    const { t } = useTranslation();
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);
    const [files, setFiles] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [apiProvider, setApiProvider] = useState('gemini');
    const [targetLang, setTargetLang] = useState('zh-CN');
    const [scanning, setScanning] = useState(false);
    const [miningStatus, setMiningStatus] = useState(null);

    useEffect(() => {
        fetchProjects();
    }, []);

    useEffect(() => {
        if (selectedProject) {
            fetchFiles(selectedProject);
            fetchMiningStatus(selectedProject);
        } else {
            setFiles([]);
            setSelectedFiles([]);
            setMiningStatus(null);
        }
    }, [selectedProject]);

    useEffect(() => {
        if (!selectedProject || miningStatus?.status !== 'running') {
            return undefined;
        }

        const intervalId = window.setInterval(() => {
            fetchMiningStatus(selectedProject);
        }, 2000);

        return () => window.clearInterval(intervalId);
    }, [selectedProject, miningStatus?.status]);

    const fetchProjects = async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
            setProjects(response.data.map(p => ({ value: p.project_id, label: p.name })));
        } catch (error) {
            console.error("Failed to fetch projects", error);
        }
    };

    const fetchFiles = async (projectId) => {
        try {
            const response = await api.get(`${API_BASE_URL}/project/${encodeURIComponent(projectId)}/files`);
            setFiles(response.data);
        } catch (error) {
            console.error("Failed to fetch files", error);
        }
    };

    const fetchMiningStatus = async (projectId) => {
        try {
            const response = await api.get(`${API_BASE_URL}/neologisms/status/${encodeURIComponent(projectId)}`);
            setMiningStatus(response.data);
        } catch (error) {
            console.error("Failed to fetch mining status", error);
        }
    };

    const handleScan = async () => {
        if (!selectedProject) return;
        setScanning(true);
        try {
            await api.post(`${API_BASE_URL}/neologisms/mine`, {
                project_id: selectedProject,
                api_provider: apiProvider,
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
            window.setTimeout(() => fetchMiningStatus(selectedProject), 1000);
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
                            onChange={setSelectedProject}
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
                            data={[
                                { value: 'gemini', label: 'Google Gemini (Recommended)' },
                                { value: 'openai', label: 'OpenAI GPT-4' },
                                { value: 'qwen', label: 'Qwen (Tongyi Qianwen)' },
                                { value: 'deepseek', label: 'DeepSeek' },
                                { value: 'grok', label: 'Grok (xAI)' },
                                { value: 'ollama', label: 'Ollama (Local)' },
                                { value: 'modelscope', label: 'ModelScope' },
                                { value: 'siliconflow', label: 'SiliconFlow' },
                                { value: 'your_favourite_api', label: 'Custom API' }
                            ]}
                            value={apiProvider}
                            onChange={setApiProvider}
                            size="md"
                        />

                        <Button
                            size="xl"
                            mt="xl"
                            leftSection={<IconRadar2 />}
                            onClick={handleScan}
                            loading={scanning}
                            disabled={!selectedProject}
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
                                        <Text size="xs">{t('neologism_review.mining.completed_terms', { count: miningStatus.new_terms || 0 })}</Text>
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

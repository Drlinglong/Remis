import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Container, Grid, Paper, Title, Text, Stack, Group, Button,
    TextInput, ScrollArea, Select, Checkbox
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
    IconRadar2, IconCpu, IconFileText, IconSparkles
} from '@tabler/icons-react';
import api from '../../utils/api';

const API_BASE_URL = '/api';

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

    useEffect(() => {
        fetchProjects();
    }, []);

    useEffect(() => {
        if (selectedProject) {
            fetchFiles(selectedProject);
        } else {
            setFiles([]);
            setSelectedFiles([]);
        }
    }, [selectedProject]);

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
            const response = await api.get(`${API_BASE_URL}/projects/${projectId}/files`);
            setFiles(response.data);
        } catch (error) {
            console.error("Failed to fetch files", error);
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
            notifications.show({
                title: t('neologism_review.mining.start_mining'),
                message: 'The AI is now mining neologisms in the background.',
                color: 'blue',
                icon: <IconSparkles size={18} />
            });
        } catch (error) {
            notifications.show({ title: 'Error', message: 'Failed to start scan', color: 'red' });
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
                            label="Target Language"
                            description="AI will provide suggestions in this language"
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
                                        {files.map(f => (
                                            <Checkbox
                                                key={f.path}
                                                value={f.path}
                                                label={
                                                    <Group gap="xs">
                                                        <IconFileText size={14} />
                                                        <Text size="sm">{f.rel_path}</Text>
                                                    </Group>
                                                }
                                            />
                                        ))}
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

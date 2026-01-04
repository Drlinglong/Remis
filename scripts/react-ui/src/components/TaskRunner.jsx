import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Text,
    Title,
    Progress,
    Paper,
    Collapse,
    Button,
    Group,
    Stack,
    ThemeIcon,
    ScrollArea,
    Code,
    useMantineTheme,
    Alert,
    SimpleGrid,
    Loader
} from '@mantine/core';
import {
    IconChevronDown,
    IconChevronUp,
    IconTerminal2,
    IconCircleCheck,
    IconAlertCircle,
    IconRefresh,
    IconLayoutDashboard,
    IconBug,
    IconBook,
    IconTypography,
    IconFolderOpen,
    IconRocket,
    IconCloudUpload
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';
import notificationService from '../services/notificationService';

const TaskRunner = ({ task, onRestart, onDashboard, translationDetails }) => {
    const { t } = useTranslation();
    const theme = useMantineTheme();
    const [showLogs, setShowLogs] = useState(false);
    const [deployStatus, setDeployStatus] = useState('idle'); // 'idle', 'loading', 'success', 'error'
    const viewport = useRef(null);

    // Auto-scroll logs
    useEffect(() => {
        if (showLogs && viewport.current) {
            viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: 'smooth' });
        }
    }, [task.log, showLogs]);

    const progress = task?.progress || {
        percent: 0,
        stage: 'Initializing',
        current_file: '',
        current: 0,
        total: 0,
        current_batch: 0,
        total_batches: 0,
        error_count: 0,
        glossary_issues: 0,
        format_issues: 0
    };

    const isCompleted = task?.status === 'completed';
    const isFailed = task?.status === 'failed';

    // Calculate remaining
    const remainingFiles = Math.max(0, progress.total - progress.current);
    const remainingBatches = Math.max(0, progress.total_batches - progress.current_batch);

    const getLocalizedStage = (stage) => {
        const map = {
            'Creating Backup': 'stage_creating_backup',
            'Translating': 'stage_translating',
            'Reading Source': 'stage_reading_source',
            'Initializing': 'stage_initializing',
            'Failed': 'stage_failed'
        };
        return t(map[stage] || stage);
    };

    const handleOpenFolder = async () => {
        if (!task?.result_path) return;
        // result_path is a zip file path, we want the directory containing it or the extracted folder
        // The backend sets result_path to the zip file.
        // However, the folder also exists at the same location without .zip extension (usually)
        // Or we can just open the parent directory of the zip.

        // Actually, let's try to open the folder that was zipped.
        // result_path: .../DEST_DIR/folder.zip
        // folder: .../DEST_DIR/folder

        const zipPath = task.result_path;
        const folderPath = zipPath.replace('.zip', '');

        try {
            await api.post('/api/system/open_folder', { path: folderPath });
        } catch (error) {
            console.error("Failed to open folder:", error);
            // Fallback: Try opening the parent directory
            try {
                // If folder doesn't exist (maybe deleted?), open parent
                const parentDir = zipPath.substring(0, zipPath.lastIndexOf('\\'));
                await api.post('/api/system/open_folder', { path: parentDir });
            } catch (e) {
                console.error("Failed to open parent folder:", e);
            }
        }
    };

    const handleDeploy = async () => {
        if (!task?.result_path || !translationDetails?.gameId) return;

        setDeployStatus('loading');

        // result_path: .../DEST_DIR/folder.zip
        // We need the folder name: folder
        const zipName = task.result_path.split(/[\\/]/).pop();
        const folderName = zipName.replace('.zip', '');

        try {
            const response = await api.post('/api/tools/deploy_mod', {
                output_folder_name: folderName,
                game_id: translationDetails.gameId
            });

            if (response.data.status === 'success') {
                setDeployStatus('success');
                notificationService.success(t('deploy_success_message'), { title: t('deploy_success_title') });
            } else {
                setDeployStatus('error');
                notificationService.error(response.data.message || 'Deployment failed', { title: t('deploy_failed_title') });
            }
        } catch (error) {
            console.error("Deployment failed:", error);
            setDeployStatus('error');
            const errorMsg = error.response?.data?.detail || error.message;
            notificationService.error(errorMsg, { title: t('deploy_failed_title') });
        }
    };

    // Render Report Card
    if (isCompleted) {
        return (
            <Stack gap="xl" mt="xl">
                <Paper p="xl" radius="lg" withBorder bg={theme.colors.dark[7]}>
                    <Stack align="center" gap="lg">
                        <ThemeIcon size={80} radius="xl" color="green" variant="light">
                            <IconCircleCheck size={50} />
                        </ThemeIcon>
                        <Title order={2}>{t('translation_completed')}</Title>
                        <Text ta="center" size="lg">
                            {t('report_success_summary', {
                                mod_name: translationDetails?.modName || 'Mod',
                                source_lang: translationDetails?.sourceLang || 'Source',
                                target_langs: translationDetails?.targetLangs?.join(', ') || 'Targets'
                            })}
                        </Text>

                        <SimpleGrid cols={3} gap="lg" w="100%" mt="md">
                            {/* Error Report */}
                            <Alert
                                icon={<IconBug size={20} />}
                                title={t('report_title_errors')}
                                color={progress.error_count > 0 ? "red" : "green"}
                                variant="light"
                            >
                                {progress.error_count > 0
                                    ? t('report_error_count', { count: progress.error_count })
                                    : t('report_no_errors')}
                            </Alert>

                            {/* Glossary Report */}
                            <Alert
                                icon={<IconBook size={20} />}
                                title={t('report_title_glossary')}
                                color={progress.glossary_issues > 0 ? "orange" : "green"}
                                variant="light"
                            >
                                {progress.glossary_issues > 0
                                    ? t('report_glossary_issues', { count: progress.glossary_issues })
                                    : t('report_no_glossary_issues')}
                            </Alert>

                            {/* Format Report */}
                            <Alert
                                icon={<IconTypography size={20} />}
                                title={t('report_title_formatting')}
                                color={progress.format_issues > 0 ? "yellow" : "green"}
                                variant="light"
                            >
                                {progress.format_issues > 0
                                    ? t('report_format_issues', { count: progress.format_issues })
                                    : t('report_no_format_issues')}
                            </Alert>
                        </SimpleGrid>

                        <Group mt="xl">
                            <Button
                                leftSection={<IconFolderOpen size={20} />}
                                size="lg"
                                color="teal"
                                onClick={handleOpenFolder}
                            >
                                {t('button_open_folder', 'Open Folder')}
                            </Button>
                            <Button
                                leftSection={deployStatus === 'loading' ? <Loader size={14} color="white" /> : <IconRocket size={20} />}
                                size="lg"
                                color={deployStatus === 'success' ? 'green' : (deployStatus === 'error' ? 'red' : 'blue')}
                                onClick={handleDeploy}
                                loading={deployStatus === 'loading'}
                                disabled={deployStatus === 'success'}
                            >
                                {deployStatus === 'loading' ? t('button_deploying') : t('button_auto_deploy')}
                            </Button>
                            <Button
                                leftSection={<IconRefresh size={20} />}
                                size="lg"
                                variant="default"
                                onClick={onRestart}
                            >
                                {t('button_translate_another')}
                            </Button>
                            <Button
                                leftSection={<IconLayoutDashboard size={20} />}
                                size="lg"
                                onClick={onDashboard}
                            >
                                {t('button_go_dashboard')}
                            </Button>
                        </Group>
                    </Stack>
                </Paper>

                {/* Log Viewer (Collapsed by default) */}
                <Button
                    variant="subtle"
                    onClick={() => setShowLogs(!showLogs)}
                    leftSection={showLogs ? <IconChevronUp /> : <IconChevronDown />}
                >
                    {showLogs ? t('hide_detailed_logs') : t('show_detailed_logs')}
                </Button>
                <Collapse in={showLogs}>
                    <Paper p="md" radius="md" withBorder bg="#1e1e1e">
                        <ScrollArea h={300} viewportRef={viewport} type="auto">
                            <Stack gap={4}>
                                {task.log && task.log.map((line, index) => (
                                    <Code key={index} block bg="transparent" c="#d4d4d4" style={{ fontSize: '0.85rem', border: 'none' }}>
                                        {line}
                                    </Code>
                                ))}
                            </Stack>
                        </ScrollArea>
                    </Paper>
                </Collapse>
            </Stack>
        );
    }

    // Render Progress Cockpit
    return (
        <Box w="100%" mt="xl">
            <Paper
                p="xl"
                radius="lg"
                withBorder
                style={{
                    textAlign: 'center',
                    position: 'relative',
                    overflow: 'hidden',
                    backgroundColor: theme.colors.dark[7]
                }}
            >
                <Stack align="center" gap="md">
                    <ThemeIcon size={60} radius="xl" color={isFailed ? "red" : "blue"} variant="light">
                        {isFailed ? <IconAlertCircle size={40} /> : <IconTerminal2 size={40} />}
                    </ThemeIcon>

                    <Title order={3}>
                        {isFailed ? t('stage_failed') : getLocalizedStage(progress.stage)}
                    </Title>

                    <Text c="dimmed" size="sm">
                        {t('progress_translating_model', {
                            model: translationDetails?.model || 'AI',
                            total_files: progress.total,
                            total_batches: progress.total_batches
                        })}
                    </Text>

                    <Text size="md" fw={500}>
                        {t('progress_status', {
                            processed_files: progress.current,
                            completed_batches: progress.current_batch,
                            remaining_files: remainingFiles,
                            remaining_batches: remainingBatches
                        })}
                    </Text>

                    {/* Progress Bar */}
                    <Box w="100%" pos="relative" mt="md">
                        <Progress
                            value={progress.percent}
                            size="xl"
                            radius="xl"
                            animated={!isFailed}
                            color={isFailed ? "red" : "blue"}
                        />
                        <Text
                            size="xs"
                            fw={700}
                            c="dimmed"
                            style={{ position: 'absolute', right: 0, top: -20 }}
                        >
                            {Math.round(progress.percent)}%
                        </Text>
                    </Box>

                    <Button
                        variant="subtle"
                        size="sm"
                        leftSection={showLogs ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
                        onClick={() => setShowLogs(!showLogs)}
                        radius="xl"
                        mt="md"
                    >
                        {showLogs ? t('hide_detailed_logs') : t('show_detailed_logs')}
                    </Button>
                </Stack>
            </Paper>

            {/* Drawer - Log Viewer */}
            <Collapse in={showLogs}>
                <Paper mt="md" p="md" radius="md" withBorder bg="#1e1e1e">
                    <ScrollArea h={300} viewportRef={viewport} type="auto">
                        <Stack gap={4}>
                            {task.log && task.log.map((line, index) => {
                                let color = '#d4d4d4';
                                if (line.includes('ERROR') || line.includes('Failed')) color = '#f48771';
                                if (line.includes('WARNING')) color = '#cca700';
                                return (
                                    <Code key={index} block bg="transparent" c={color} style={{ fontSize: '0.85rem', border: 'none' }}>
                                        {line}
                                    </Code>
                                );
                            })}
                        </Stack>
                    </ScrollArea>
                </Paper>
            </Collapse>
        </Box>
    );
};

export default TaskRunner;

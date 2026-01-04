import React from 'react';
import { useTranslation } from 'react-i18next';
import { Stack, Group, Text, Title, Paper, Anchor, Alert, ThemeIcon, List, Box, Divider, Button } from '@mantine/core';
import { IconBrandGithub, IconInfoCircle, IconStar, IconBug, IconFileCode, IconFolderOpen } from '@tabler/icons-react';
import api from '../utils/api';
import { notifications } from '@mantine/notifications';

const VersionInfoTab = () => {
    const { t } = useTranslation();
    const version = "v2.0.0 Technical Preview"; // Project version
    const lastUpdated = "2026-01-04"; // Last updated date
    const githubRepoUrl = "https://github.com/Drlinglong/V3_Mod_Localization_Factory";

    const handleOpenLogs = async () => {
        try {
            await api.post('/api/system/open-logs');
        } catch (error) {
            notifications.show({
                title: 'Error',
                message: 'Failed to open logs directory',
                color: 'red'
            });
        }
    };

    const handleOpenUrl = async (url) => {
        try {
            await api.post('/api/system/open-url', { url });
        } catch (error) {
            window.open(url, '_blank'); // Fallback
        }
    };

    return (
        <Stack gap="xl" py="md">
            {/* Project Summary */}
            <Paper withBorder p="lg" radius="md" style={{ background: 'rgba(255, 255, 255, 0.05)', backdropFilter: 'blur(10px)' }}>
                <Group justify="space-between" align="flex-start">
                    <Stack gap={0}>
                        <Title order={3}>{t('app_title')}</Title>
                        <Group gap="xs" mt="xs">
                            <Text size="sm" c="dimmed">{t('version_info.project_version')}:</Text>
                            <Text size="sm" fw={700} c="cyan">{version}</Text>
                        </Group>
                        <Group gap="xs">
                            <Text size="sm" c="dimmed">{t('version_info.last_updated')}:</Text>
                            <Text size="sm">{lastUpdated}</Text>
                        </Group>
                    </Stack>
                    <Anchor component="button" onClick={() => handleOpenUrl(githubRepoUrl)}>
                        <ThemeIcon size={48} radius="xl" variant="light" color="gray">
                            <IconBrandGithub size={30} />
                        </ThemeIcon>
                    </Anchor>
                </Group>

                <Divider my="lg" opacity={0.5} />

                <Group justify="space-between">
                    <Group gap="xs">
                        <IconStar size={20} color="var(--mantine-color-yellow-filled)" />
                        <Text size="sm">
                            {t('version_info.star_encouragement').split('Star').map((part, i, arr) => (
                                <React.Fragment key={i}>
                                    {part}
                                    {i < arr.length - 1 && <Text span fw={700} c="yellow">Star</Text>}
                                </React.Fragment>
                            ))}
                        </Text>
                    </Group>
                    <Anchor component="button" onClick={() => handleOpenUrl(githubRepoUrl)} size="sm">
                        {t('version_info.github_link_text')}
                    </Anchor>
                </Group>
            </Paper>

            {/* Feedback & Integrity */}
            <Alert
                icon={<IconBug size={20} />}
                title={t('version_info.issue_title')}
                color="blue"
                radius="md"
                variant="light"
            >
                <Stack gap="xs">
                    <Text size="sm">
                        {t('version_info.issue_desc')}
                    </Text>
                    <Box
                        p="xs"
                        style={{
                            background: 'rgba(0, 0, 0, 0.2)',
                            borderRadius: '4px',
                            border: '1px solid rgba(255, 255, 255, 0.1)'
                        }}
                    >
                        <Group gap="xs" align="flex-start">
                            <IconFileCode size={18} style={{ marginTop: 2 }} />
                            <Text size="xs" style={{ whiteSpace: 'pre-wrap' }}>
                                <Text span fw={700} c="blue" style={{ fontSize: '1.2em' }}>💡</Text> {' '}
                                {t('version_info.log_hint')}
                            </Text>
                        </Group>
                    </Box>
                    <Group grow>
                        <Button
                            leftSection={<IconFolderOpen size={16} />}
                            variant="light"
                            color="blue"
                            onClick={handleOpenLogs}
                        >
                            {t('version_info.open_logs_btn')}
                        </Button>
                        <Button
                            variant="subtle"
                            fw={700}
                            onClick={() => handleOpenUrl(`${githubRepoUrl}/issues`)}
                        >
                            Go to Issues
                        </Button>
                    </Group>
                </Stack>
            </Alert>

            {/* Credits / Additional Links can go here */}
            <Paper p="md" radius="md" style={{ background: 'transparent' }}>
                <Text size="xs" c="dimmed" ta="center">
                    {t('footer_text')}
                </Text>
            </Paper>
        </Stack>
    );
};

export default VersionInfoTab;

import React, { useContext, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Select, Group, Title, Text, Container, Paper, Stack, Divider, Tabs, Box, Button, Modal } from '@mantine/core';
import api from '../utils/api';
import { IconLanguage, IconPalette, IconSettings, IconKey, IconMessage, IconInfoCircle } from '@tabler/icons-react';
import ThemeContext from '../ThemeContext';
import { AVAILABLE_THEMES } from '../config/themes';
import ApiSettingsTab from '../components/ApiSettingsTab';
import PromptSettingsTab from '../components/PromptSettingsTab';
import VersionInfoTab from '../components/VersionInfoTab';
import { useTutorial, getTutorialKey } from '../context/TutorialContext';

import styles from './SettingsPage.module.css';


const SettingsPage = () => {
    const { t, i18n } = useTranslation();
    const { theme, toggleTheme } = useContext(ThemeContext);
    const { startTour, setPageContext } = useTutorial();
    const [resetModalOpen, setResetModalOpen] = React.useState(false);
    const [showTutorialPrompt, setShowTutorialPrompt] = React.useState(false);
    const [activeTab, setActiveTab] = React.useState('general');
    const [rpmLimit, setRpmLimit] = React.useState('40');

    useEffect(() => {
        const savedLanguage = localStorage.getItem('language');
        if (savedLanguage) {
            i18n.changeLanguage(savedLanguage);
        }

        const context = activeTab === 'api' ? 'settings-api' : 'settings';
        setPageContext(context);

        // Fetch current RPM limit
        const fetchRpm = async () => {
            try {
                const response = await api.get('/api/config');
                if (response.data && response.data.rpm_limit) {
                    setRpmLimit(response.data.rpm_limit.toString());
                }
            } catch (err) {
                console.error("Failed to fetch RPM limit:", err);
            }
        };
        fetchRpm();

        // Check for first-time user on this page
        const tutorialKey = getTutorialKey(`${context}_prompt_seen`);
        const hasSeenTutorialPrompt = localStorage.getItem(tutorialKey);
        if (!hasSeenTutorialPrompt) {
            setShowTutorialPrompt(true);
        }
    }, [i18n, setPageContext, activeTab]);

    const handleLanguageChange = (value) => {
        i18n.changeLanguage(value);
        localStorage.setItem('language', value);
    };

    const handleThemeChange = (value) => {
        toggleTheme(value);
    };

    const handleRpmChange = async (value) => {
        setRpmLimit(value);
        try {
            await api.post('/api/config/rpm', { rpm: parseInt(value) });
        } catch (err) {
            console.error("Failed to update RPM limit:", err);
        }
    };

    return (
        <Box style={{ flex: 1, overflowY: 'auto', height: '100%' }}>
            <Container fluid py="xl">
                <Paper withBorder p="xl" radius="md" className={styles.glassCard}>
                    <Title order={2} mb="xl" className={styles.headerTitle}>{t('page_title_settings')}</Title>

                    <Tabs value={activeTab} onChange={setActiveTab}>
                        <Tabs.List mb="lg">
                            <Tabs.Tab id="settings-tab-general" value="general" leftSection={<IconSettings size={16} />}>
                                {t('settings_general') || 'General'}
                            </Tabs.Tab>
                            <Tabs.Tab id="settings-tab-api" value="api" leftSection={<IconKey size={16} />}>
                                {t('settings_api') || 'API Settings'}
                            </Tabs.Tab>
                            <Tabs.Tab value="prompts" leftSection={<IconMessage size={16} />}>
                                {t('settings_prompts') || 'Prompt Settings'}
                            </Tabs.Tab>
                            <Tabs.Tab id="settings-tab-version" value="version" leftSection={<IconInfoCircle size={16} />}>
                                {t('version_info.tab_title') || 'Version Info'}
                            </Tabs.Tab>
                        </Tabs.List>

                        <Tabs.Panel value="general">
                            <Stack gap="lg">
                                <Group justify="space-between">
                                    <Group>
                                        <IconLanguage size={20} />
                                        <Text fw={500}>{t('settings_language')}</Text>
                                    </Group>
                                    <Select
                                        value={i18n.language}
                                        onChange={handleLanguageChange}
                                        data={[
                                            { value: 'en', label: 'English (en-US)' },
                                            { value: 'zh', label: '简体中文 (zh-CN)' },
                                        ]}
                                        style={{ width: 200 }}
                                    />
                                </Group>

                                <Divider />

                                <Group id="settings-theme-group" justify="space-between">
                                    <Group>
                                        <IconPalette size={20} />
                                        <Text fw={500}>{t('settings_theme')}</Text>
                                    </Group>
                                    <Select
                                        value={theme}
                                        onChange={handleThemeChange}
                                        data={AVAILABLE_THEMES.map(theme => ({ value: theme.id, label: t(theme.nameKey) }))}
                                        style={{ width: 200 }}
                                    />
                                </Group>

                                <Divider />

                                <Group justify="space-between">
                                    <Group>
                                        <IconSettings size={20} />
                                        <Box>
                                            <Text fw={500}>{t('settings_rpm_limit') || "Global RPM Limit"}</Text>
                                            <Text size="xs" c="dimmed">{t('settings_rpm_limit_desc') || "Requests Per Minute (Shared by all providers)"}</Text>
                                        </Box>
                                    </Group>
                                    <Select
                                        value={rpmLimit}
                                        onChange={handleRpmChange}
                                        data={[
                                            { value: '5', label: '5 RPM' },
                                            { value: '10', label: '10 RPM' },
                                            { value: '20', label: '20 RPM' },
                                            { value: '40', label: '40 RPM' },
                                            { value: '100', label: '100 RPM' },
                                            { value: '200', label: '200 RPM' },
                                        ]}
                                        style={{ width: 200 }}
                                    />
                                </Group>

                                <Divider my="xl" label={t('settings_system_maintenance')} labelPosition="center" />

                                <Group justify="space-between">
                                    <Box>
                                        <Text fw={500} c="red">{t('settings_reset_db_title')}</Text>
                                        <Text size="sm" c="dimmed">
                                            {t('settings_reset_db_desc')}
                                        </Text>
                                    </Box>
                                    <Button color="red" variant="light" onClick={() => setResetModalOpen(true)}>
                                        {t('btn_reset_db')}
                                    </Button>
                                </Group>
                            </Stack>
                        </Tabs.Panel>

                        <Tabs.Panel value="api">
                            <ApiSettingsTab />
                        </Tabs.Panel>

                        <Tabs.Panel value="prompts">
                            <PromptSettingsTab />
                        </Tabs.Panel>

                        <Tabs.Panel value="version">
                            <VersionInfoTab />
                        </Tabs.Panel>
                    </Tabs>
                </Paper>
            </Container>

            <Modal
                opened={resetModalOpen}
                onClose={() => setResetModalOpen(false)}
                title={<Text c="red" fw={700}>{t('modal_reset_db_title')}</Text>}
                centered
            >
                <Stack>
                    <Text size="sm">
                        {t('modal_reset_db_confirm_text')}
                    </Text>
                    <Text size="sm" fw={700}>
                        This action will:
                    </Text>
                    <ul style={{ fontSize: '0.9em', marginTop: 0 }}>
                        <li>Remove all projects from the "Open Recent" list.</li>
                        <li>Clear all file status (Todo/Done/Proofreading) in the dashboard.</li>
                    </ul>
                    <Text size="sm" fw={700} c="green">
                        This action will NOT:
                    </Text>
                    <ul style={{ fontSize: '0.9em', marginTop: 0 }}>
                        <li>Delete your translations.</li>
                        <li>Delete your source files.</li>
                        <li>Modify any file on your disk.</li>
                    </ul>

                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={() => setResetModalOpen(false)}>Cancel</Button>
                        <Button color="red" onClick={async () => {
                            try {
                                await api.post('/api/system/reset-db');
                                setResetModalOpen(false);
                                alert("Database reset successfully. The application will now reload.");
                                window.location.reload();
                            } catch (e) {
                                alert("Failed to reset database: " + e.message);
                            }
                        }}>
                            Confirm Reset
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={showTutorialPrompt}
                onClose={() => {
                    setShowTutorialPrompt(false);
                    const context = activeTab === 'api' ? 'settings-api' : 'settings';
                    localStorage.setItem(getTutorialKey(`${context}_prompt_seen`), 'true');
                }}
                title={t('tutorial.auto_start_prompt.title')}
                centered
                radius="md"
            >
                <Stack>
                    <Text size="sm">
                        {t('tutorial.auto_start_prompt.message')}
                    </Text>
                    <Group justify="flex-end" mt="md">
                        <Button variant="subtle" color="gray" onClick={() => {
                            setShowTutorialPrompt(false);
                            const context = activeTab === 'api' ? 'settings-api' : 'settings';
                            localStorage.setItem(getTutorialKey(`${context}_prompt_seen`), 'true');
                        }}>
                            {t('tutorial.auto_start_prompt.cancel')}
                        </Button>
                        <Button color="blue" onClick={() => {
                            setShowTutorialPrompt(false);
                            const context = activeTab === 'api' ? 'settings-api' : 'settings';
                            localStorage.setItem(getTutorialKey(`${context}_prompt_seen`), 'true');
                            startTour(context);
                        }}>
                            {t('tutorial.auto_start_prompt.confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </Box >
    );
};

export default SettingsPage;
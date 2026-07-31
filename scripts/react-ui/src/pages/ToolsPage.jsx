import React, { Suspense, lazy } from 'react';
import { useTranslation } from 'react-i18next';
import { Center, Loader, Modal, Stack, Text, Group, Button, Tabs, Title, Container, Paper } from '@mantine/core';
import { IconBug, IconCode } from '@tabler/icons-react';
import layoutStyles from '../components/layout/Layout.module.css';
import { FEATURES } from '../config/features';
import { useTutorial, getTutorialKey } from '../context/TutorialContextCore';

const EventRenderer = lazy(() => import('./EventRenderer'));
const UIDebugger = lazy(() => import('./UIDebugger'));

const ToolPanelFallback = () => (
    <Center h={240}>
        <Loader type="dots" />
    </Center>
);

const ToolsPage = () => {
    const { t } = useTranslation();
    const { startTour, setPageContext } = useTutorial();
    const [showTutorialPrompt, setShowTutorialPrompt] = React.useState(false);
    const [activeTab, setActiveTab] = React.useState('event');

    React.useEffect(() => {
        setPageContext('tools');
        // Check for first-time user on this page
        const tutorialKey = getTutorialKey('tools_prompt_seen');
        const hasSeenTutorialPrompt = localStorage.getItem(tutorialKey);
        if (!hasSeenTutorialPrompt) {
            setShowTutorialPrompt(true);
        }
    }, [setPageContext]);

    return (
        <Container size="lg" py="xl">
            <Paper withBorder p="xl" radius="md" className={layoutStyles.glassCard}>
                <Title order={2} mb="xl">{t('page_title_tools')}</Title>
                <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'thumbnail')} variant="pills" radius="md" keepMounted={false}>
                    <Tabs.List id="tools-tabs-list" mb="lg">
                        {FEATURES.ENABLE_EVENT_RENDERER && (
                            <Tabs.Tab value="event" leftSection={<IconCode size={16} />}>{t('tools_tab_event_renderer')}</Tabs.Tab>
                        )}

                        {FEATURES.ENABLE_UI_DEBUGGER && (
                            <Tabs.Tab value="debugger" leftSection={<IconBug size={16} />}>{t('tools_tab_ui_debugger')}</Tabs.Tab>
                        )}
                    </Tabs.List>

                    {FEATURES.ENABLE_EVENT_RENDERER && (
                        <Tabs.Panel value="event">
                            <Suspense fallback={<ToolPanelFallback />}>
                                {activeTab === 'event' && <EventRenderer />}
                            </Suspense>
                        </Tabs.Panel>
                    )}

                    {FEATURES.ENABLE_UI_DEBUGGER && (
                        <Tabs.Panel value="debugger">
                            <Suspense fallback={<ToolPanelFallback />}>
                                {activeTab === 'debugger' && <UIDebugger />}
                            </Suspense>
                        </Tabs.Panel>
                    )}
                </Tabs>
            </Paper>

            <Modal
                opened={showTutorialPrompt}
                onClose={() => {
                    setShowTutorialPrompt(false);
                    localStorage.setItem(getTutorialKey('tools_prompt_seen'), 'true');
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
                            localStorage.setItem(getTutorialKey('tools_prompt_seen'), 'true');
                        }}>
                            {t('tutorial.auto_start_prompt.cancel')}
                        </Button>
                        <Button color="blue" onClick={() => {
                            setShowTutorialPrompt(false);
                            localStorage.setItem(getTutorialKey('tools_prompt_seen'), 'true');
                            startTour('tools');
                        }}>
                            {t('tutorial.auto_start_prompt.confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </Container>
    );
};

export default ToolsPage;

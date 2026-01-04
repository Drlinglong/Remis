import React from 'react';
import { useTranslation } from 'react-i18next';
import { Modal, Stack, Text, Group, Button, Tabs, Title, Container, Paper } from '@mantine/core';
import { IconPhoto, IconTools, IconBug, IconCode } from '@tabler/icons-react';
import ThumbnailGenerator from '../components/tools/ThumbnailGenerator';
import WorkshopGenerator from '../components/tools/WorkshopGenerator';
import EventRenderer from './EventRenderer';
import UIDebugger from './UIDebugger';
import layoutStyles from '../components/layout/Layout.module.css';
import { FEATURES } from '../config/features';
import { useTutorial, getTutorialKey } from '../context/TutorialContext';

const ToolsPage = () => {
    const { t } = useTranslation();
    const { startTour, setPageContext } = useTutorial();
    const [showTutorialPrompt, setShowTutorialPrompt] = React.useState(false);

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
                <Tabs defaultValue="thumbnail" variant="pills" radius="md">
                    <Tabs.List id="tools-tabs-list" mb="lg">
                        <Tabs.Tab value="thumbnail" leftSection={<IconPhoto size={16} />}>{t('tools_tab_thumbnail_generator')}</Tabs.Tab>

                        {FEATURES.ENABLE_WORKSHOP_GENERATOR && (
                            <Tabs.Tab value="workshop" leftSection={<IconTools size={16} />}>{t('tools_tab_workshop_generator')}</Tabs.Tab>
                        )}

                        {FEATURES.ENABLE_EVENT_RENDERER && (
                            <Tabs.Tab value="event" leftSection={<IconCode size={16} />}>{t('tools_tab_event_renderer')}</Tabs.Tab>
                        )}

                        {FEATURES.ENABLE_UI_DEBUGGER && (
                            <Tabs.Tab value="debugger" leftSection={<IconBug size={16} />}>{t('tools_tab_ui_debugger')}</Tabs.Tab>
                        )}
                    </Tabs.List>

                    <Tabs.Panel value="thumbnail">
                        <ThumbnailGenerator />
                    </Tabs.Panel>

                    {FEATURES.ENABLE_WORKSHOP_GENERATOR && (
                        <Tabs.Panel value="workshop">
                            <WorkshopGenerator />
                        </Tabs.Panel>
                    )}

                    {FEATURES.ENABLE_EVENT_RENDERER && (
                        <Tabs.Panel value="event">
                            <EventRenderer />
                        </Tabs.Panel>
                    )}

                    {FEATURES.ENABLE_UI_DEBUGGER && (
                        <Tabs.Panel value="debugger">
                            <UIDebugger />
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
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { Box, Group, Stack, Tabs, Text, ThemeIcon, Title } from '@mantine/core';
import { IconCpu, IconGavel } from '@tabler/icons-react';
import MiningDashboard from '../components/neologism/MiningDashboard';
import JudgmentCourt from '../components/neologism/JudgmentCourt';
import {
    getNeologismReviewSession,
    updateNeologismReviewSession,
} from './neologismReviewSession';
import { useTutorial } from '../context/TutorialContextCore';

/**
 * 新词审核页面
 * 轻量级容器，仅负责 Tab 切换和布局
 */
const NeologismReviewPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { setPageContext } = useTutorial();
    const [activeTab, setActiveTab] = useState(
        () => getNeologismReviewSession().activeTab,
    );
    const [selectedProject, setSelectedProject] = useState(
        () => getNeologismReviewSession().selectedProject,
    );
    const [courtRefreshToken, setCourtRefreshToken] = useState(0);

    useEffect(() => {
        setPageContext(activeTab === 'court' ? 'neologism-court' : 'neologism-mining');
    }, [activeTab, setPageContext]);

    const handleActiveTabChange = useCallback((nextTab) => {
        const resolvedTab = nextTab || 'dashboard';
        updateNeologismReviewSession({ activeTab: resolvedTab });
        setActiveTab(resolvedTab);
    }, []);

    const handleSelectedProjectChange = useCallback((projectId) => {
        updateNeologismReviewSession({ selectedProject: projectId });
        setSelectedProject(projectId);
    }, []);

    const handleMiningComplete = useCallback(() => {
        setCourtRefreshToken((value) => value + 1);
        updateNeologismReviewSession({ activeTab: 'court' });
        setActiveTab('court');
    }, []);

    const handleOpenMining = useCallback(() => {
        updateNeologismReviewSession({ activeTab: 'dashboard' });
        setActiveTab('dashboard');
    }, []);

    const handleOpenGlossary = useCallback(({ gameId, glossaryId }) => {
        if (!gameId || !glossaryId) return;
        navigate(
            `/glossary-manager?game_id=${encodeURIComponent(gameId)}&glossary_id=${encodeURIComponent(glossaryId)}`
        );
    }, [navigate]);

    return (
        <Box
            h="100%"
            data-neologism-layout="compact"
            data-remis-surface="canvas"
            style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}
        >
            <Group id="neologism-page-header" px="md" pt="sm" gap="xs" align="center" wrap="nowrap" style={{ flexShrink: 0 }}>
                <ThemeIcon size="md" radius="sm" variant="light" color="blue">
                    <IconGavel size={18} />
                </ThemeIcon>
                <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
                    <Title
                        order={1}
                        lineClamp={1}
                        style={{ fontSize: 'clamp(1.35rem, 2.2vw, 1.8rem)', lineHeight: 1.15 }}
                    >
                        {t('neologism_review.title')}
                    </Title>
                    <Text size="xs" c="dimmed" lineClamp={1}>{t('neologism_review.subtitle')}</Text>
                </Stack>
            </Group>
            <Tabs
                value={activeTab}
                onChange={handleActiveTabChange}
                variant="pills"
                radius="md"
                style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: '1 1 0' }}
            >
                <Box id="neologism-page-tabs" px="md" pt="xs" style={{ flexShrink: 0 }}>
                    <Tabs.List>
                        <Tabs.Tab value="dashboard" leftSection={<IconCpu size={16} />}>
                            {t('neologism_review.tab_mining')}
                        </Tabs.Tab>
                        <Tabs.Tab value="court" leftSection={<IconGavel size={16} />}>
                            {t('neologism_review.tab_court')}
                        </Tabs.Tab>
                    </Tabs.List>
                </Box>

                <Tabs.Panel
                    id="neologism-mining-panel"
                    value="dashboard"
                    style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}
                >
                    <MiningDashboard
                        selectedProject={selectedProject}
                        onSelectedProjectChange={handleSelectedProjectChange}
                        onMiningComplete={handleMiningComplete}
                    />
                </Tabs.Panel>

                <Tabs.Panel
                    id="neologism-court-panel"
                    value="court"
                    style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}
                >
                    <JudgmentCourt
                        selectedProject={selectedProject}
                        onSelectedProjectChange={handleSelectedProjectChange}
                        refreshToken={courtRefreshToken}
                        onOpenMining={handleOpenMining}
                        onOpenGlossary={handleOpenGlossary}
                    />
                </Tabs.Panel>
            </Tabs>
        </Box>
    );
};

export default NeologismReviewPage;

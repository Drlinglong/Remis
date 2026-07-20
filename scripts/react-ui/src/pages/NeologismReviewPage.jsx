import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Box, Group, Stack, Tabs, Text, ThemeIcon, Title } from '@mantine/core';
import { IconCpu, IconGavel } from '@tabler/icons-react';
import MiningDashboard from '../components/neologism/MiningDashboard';
import JudgmentCourt from '../components/neologism/JudgmentCourt';

/**
 * 新词审核页面
 * 轻量级容器，仅负责 Tab 切换和布局
 */
const NeologismReviewPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState('dashboard');
    const [selectedProject, setSelectedProject] = useState(null);
    const [courtRefreshToken, setCourtRefreshToken] = useState(0);

    const handleMiningComplete = useCallback(() => {
        setCourtRefreshToken((value) => value + 1);
        setActiveTab('court');
    }, []);

    const handleOpenMining = useCallback(() => {
        setActiveTab('dashboard');
    }, []);

    const handleOpenGlossary = useCallback(({ gameId, glossaryId }) => {
        if (!gameId || !glossaryId) return;
        navigate(
            `/glossary-manager?game_id=${encodeURIComponent(gameId)}&glossary_id=${encodeURIComponent(glossaryId)}`
        );
    }, [navigate]);

    return (
        <Box h="100%" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Group px="md" pt="md" gap="sm" align="center" wrap="nowrap" style={{ flexShrink: 0 }}>
                <ThemeIcon size="xl" radius="md" variant="light" color="blue">
                    <IconGavel size={24} />
                </ThemeIcon>
                <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
                    <Title
                        order={1}
                        lineClamp={1}
                        style={{ fontSize: 'clamp(2rem, 4vw, 3.25rem)' }}
                    >
                        {t('neologism_review.title')}
                    </Title>
                    <Text size="sm" c="dimmed" lineClamp={1}>{t('neologism_review.subtitle')}</Text>
                </Stack>
            </Group>
            <Tabs
                value={activeTab}
                onChange={setActiveTab}
                variant="pills"
                radius="md"
                style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: '1 1 0' }}
            >
                <Box p="md" pb={0} style={{ flexShrink: 0 }}>
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
                    value="dashboard"
                    style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}
                >
                    <MiningDashboard
                        selectedProject={selectedProject}
                        onSelectedProjectChange={setSelectedProject}
                        onMiningComplete={handleMiningComplete}
                    />
                </Tabs.Panel>

                <Tabs.Panel
                    value="court"
                    style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}
                >
                    <JudgmentCourt
                        selectedProject={selectedProject}
                        onSelectedProjectChange={setSelectedProject}
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

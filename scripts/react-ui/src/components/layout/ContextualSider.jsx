import React, { useEffect, useState } from 'react';
import { ActionIcon, Box, Drawer, Group, SegmentedControl, Text } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { IconHistory, IconInfoCircle, IconLayoutSidebarRightCollapse, IconLayoutSidebarRightExpand } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router';

import { useSidebar } from '../../context/SidebarContextCore';
import styles from './Layout.module.css';

export function ContextualSider() {
    const location = useLocation();
    const { t } = useTranslation();
    const isCompact = useMediaQuery('(max-width: 900px)');
    const { sidebarContent, sidebarWidth, sidebarCollapsed, setSidebarCollapsed } = useSidebar();
    const [activeTab, setActiveTab] = useState('info');
    const path = location.pathname;
    let content = null;

    useEffect(() => {
        setSidebarCollapsed(true);
    }, [path, setSidebarCollapsed]);

    if (path.startsWith('/translation')) {
        content = {
            title: t('context_sidebar.translation_context', 'Translation Context'),
            info: t('context_sidebar.translation_info', 'Select a mod to see details here.'),
            history: t('context_sidebar.translation_history', 'Translation logs will appear here.'),
        };
    } else if (path.startsWith('/project-management') || path === '/') {
        content = {
            title: t('context_sidebar.project_details', 'Project Details'),
            info: t('context_sidebar.project_info', 'Select a project task to view properties.'),
            history: t('context_sidebar.project_history', 'Recent project activity.'),
        };
    } else if (path.startsWith('/glossary-manager')) {
        content = {
            title: t('context_sidebar.glossary_term', 'Glossary Term'),
            info: t('context_sidebar.glossary_info', 'Select a term to view definitions and variants.'),
            history: t('context_sidebar.glossary_history', 'Term edit history.'),
        };
    }

    if (!content) return null;

    const rail = (
        <Box
            className={`${styles.sidebarRight} ${isCompact ? styles.sidebarCompactRail : ''}`}
            style={{
                width: 50,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                paddingTop: '16px',
                flexShrink: 0,
            }}
        >
            <ActionIcon
                variant="subtle"
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                className={styles.icon}
                aria-label={sidebarCollapsed ? t('context_sidebar.expand') : t('context_sidebar.collapse')}
                title={sidebarCollapsed ? t('context_sidebar.expand') : t('context_sidebar.collapse')}
            >
                {sidebarCollapsed ? <IconLayoutSidebarRightExpand size={20} /> : <IconLayoutSidebarRightCollapse size={20} />}
            </ActionIcon>
            {sidebarCollapsed && <div id="glossary-detail-portal" style={{ display: 'none' }} />}
        </Box>
    );

    const body = (
        <>
            <Box p="xs">
                <SegmentedControl
                    fullWidth
                    size="xs"
                    value={activeTab}
                    onChange={setActiveTab}
                    data={[
                        { label: t('context_sidebar.tab_info', 'Info'), value: 'info', icon: <IconInfoCircle size={14} /> },
                        { label: t('context_sidebar.tab_history', 'History'), value: 'history', icon: <IconHistory size={14} /> },
                    ]}
                    styles={{
                        root: { backgroundColor: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)' },
                        label: { color: 'var(--text-muted)' },
                        control: { border: 'none' },
                        indicator: { backgroundColor: 'var(--color-primary)', opacity: 0.3 },
                    }}
                />
            </Box>
            <Box style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '16px' }}>
                {activeTab === 'info' ? (
                    sidebarContent || (
                        <>
                            <div id="glossary-detail-portal" />
                            <Text size="sm" c="var(--text-main)">{content.info}</Text>
                        </>
                    )
                ) : (
                    <Text size="sm" c="var(--text-main)">{content.history}</Text>
                )}
            </Box>
        </>
    );

    if (sidebarCollapsed) return rail;

    if (isCompact) {
        return (
            <>
                {rail}
                <Drawer
                    opened
                    onClose={() => setSidebarCollapsed(true)}
                    position="right"
                    size="min(380px, 92vw)"
                    title={content.title}
                    overlayProps={{ backgroundOpacity: 0.58, blur: 2 }}
                    styles={{ content: { background: 'var(--elevated-bg, var(--surface-bg))', color: 'var(--surface-text-main)' } }}
                >
                    <Box h="calc(100vh - 90px)" style={{ display: 'flex', flexDirection: 'column' }} data-remis-surface="elevated">
                        {body}
                    </Box>
                </Drawer>
            </>
        );
    }

    return (
        <>
            {rail}
            <Box
                className={`${styles.sidebarRight} ${styles.sidebarOverlay}`}
                style={{ width: sidebarWidth, display: 'flex', flexDirection: 'column' }}
            >
                <Group justify="space-between" p="md" style={{ borderBottom: '1px solid var(--glass-border)' }}>
                    <Text fw={600} size="sm" className={styles.sidebarHeader}>{content.title}</Text>
                    <ActionIcon
                        variant="subtle"
                        size="sm"
                        onClick={() => setSidebarCollapsed(true)}
                        className={styles.icon}
                        aria-label={t('context_sidebar.collapse')}
                    >
                        <IconLayoutSidebarRightCollapse size={16} />
                    </ActionIcon>
                </Group>
                {body}
            </Box>
        </>
    );
}

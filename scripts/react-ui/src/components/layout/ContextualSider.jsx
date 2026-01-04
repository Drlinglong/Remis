import React, { useState, useEffect } from 'react';
import { Box, Text, ScrollArea, SegmentedControl, Stack, Group, ActionIcon, Tooltip } from '@mantine/core';
import { IconInfoCircle, IconHistory, IconX, IconLayoutSidebarRightCollapse, IconLayoutSidebarRightExpand } from '@tabler/icons-react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSidebar } from '../../context/SidebarContext';
import styles from './Layout.module.css';

export function ContextualSider() {
    const location = useLocation();
    const { t } = useTranslation();
    const { sidebarContent, sidebarWidth, sidebarCollapsed, setSidebarCollapsed } = useSidebar();
    const [activeTab, setActiveTab] = useState('info');
    const [content, setContent] = useState(null);

    // Determine content based on route
    useEffect(() => {
        const path = location.pathname;

        if (path.startsWith('/translation')) {
            setContent({
                title: t('context_sidebar.translation_context', 'Translation Context'),
                info: t('context_sidebar.translation_info', 'Select a mod to see details here.'),
                history: t('context_sidebar.translation_history', 'Translation logs will appear here.')
            });
        } else if (path.startsWith('/project-management') || path === '/') {
            setContent({
                title: t('context_sidebar.project_details', 'Project Details'),
                info: t('context_sidebar.project_info', 'Select a project task to view properties.'),
                history: t('context_sidebar.project_history', 'Recent project activity.')
            });
        } else if (path.startsWith('/glossary-manager')) {
            setContent({
                title: t('context_sidebar.glossary_term', 'Glossary Term'),
                info: t('context_sidebar.glossary_info', 'Select a term to view definitions and variants.'),
                history: t('context_sidebar.glossary_history', 'Term edit history.')
            });
        } else {
            setContent(null); // Hide for pages without context
        }
    }, [location.pathname, t]);

    if (!content) return null;

    if (sidebarCollapsed) {
        return (
            <Box
                className={styles.sidebarRight}
                style={{
                    width: 50,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    paddingTop: '16px',
                    transition: 'width 0.3s ease',
                }}
            >
                <Tooltip label="Expand Context" position="left">
                    <ActionIcon variant="subtle" onClick={() => setSidebarCollapsed(false)} className={styles.icon}>
                        <IconLayoutSidebarRightExpand size={20} />
                    </ActionIcon>
                </Tooltip>
                {/* Always render portal target if content exists, even if collapsed, to avoid portal failures */}
                <div id="glossary-detail-portal" style={{ display: 'none' }} />
            </Box>
        );
    }

    return (
        <Box
            className={styles.sidebarRight}
            style={{
                width: sidebarCollapsed ? 50 : sidebarWidth,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'width 0.3s ease',
            }}
        >
            {/* Header */}
            <Group justify="space-between" p="md" style={{ borderBottom: '1px solid var(--glass-border)' }}>
                <Text fw={600} size="sm" className={styles.sidebarHeader}>{content.title}</Text>
                <Tooltip label="Collapse" position="left">
                    <ActionIcon variant="subtle" size="sm" onClick={() => setSidebarCollapsed(true)} className={styles.icon}>
                        <IconLayoutSidebarRightCollapse size={16} />
                    </ActionIcon>
                </Tooltip>
            </Group>

            {/* Tabs */}
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
                        indicator: { backgroundColor: 'var(--color-primary)', opacity: 0.3 }
                    }}
                />
            </Box>

            {/* Content Area */}
            <ScrollArea style={{ flex: 1 }} p="md">
                {activeTab === 'info' ? (
                    sidebarContent || (
                        <>
                            <div id="glossary-detail-portal" />
                            {!document.getElementById('glossary-detail-portal')?.hasChildNodes() && (
                                <Text size="sm" c="var(--text-main)">
                                    {content.info}
                                </Text>
                            )}
                        </>
                    )
                ) : (
                    <Text size="sm" c="var(--text-main)">
                        {content.history}
                    </Text>
                )}
            </ScrollArea>
        </Box>
    );
}

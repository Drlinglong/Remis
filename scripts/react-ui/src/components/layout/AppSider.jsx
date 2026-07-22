import React, { useState } from 'react';
import { ActionIcon, Badge, Box, Menu, Stack, Text, UnstyledButton, rem } from '@mantine/core';
import {
    IconHome,
    IconBook,
    IconLanguage,
    IconVocabulary,
    IconChecklist,
    IconBriefcase,
    IconGitBranch,
    IconTools,
    IconSettings,
    IconCrane,
    IconBulb,
    IconCode,
    IconSparkles,
    IconQuestionMark,
    IconRocket,
    IconRobot,
    IconRadar,
    IconPin,
    IconPinFilled,
    IconMessageChatbot,
    IconActivity,
    IconChevronRight,
    IconDots,
} from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import styles from './Layout.module.css';
import { FEATURES } from '../../config/features';
import { useTutorial } from '../../context/TutorialContextCore';
import { useTaskCenter } from '../../context/TaskCenterContextCore';

const primaryNavItems = [
    { icon: IconHome, label: 'page_title_home', path: '/' },
    { icon: IconBriefcase, label: 'page_title_project_management', path: '/project-management' },
];

const workflowItems = [
    { icon: IconLanguage, label: 'page_title_translation', path: '/translation' },
    ...(FEATURES.ENABLE_INCREMENTAL_TRANSLATION ? [{ icon: IconRocket, label: 'incremental_translation.title', path: '/incremental-translation' }] : []),
];

const qualityNavItems = [
    { icon: IconChecklist, label: 'page_title_proofreading', path: '/proofreading' },
    { icon: IconVocabulary, label: 'page_title_glossary_manager', path: '/glossary-manager' },
];

const moreNavItems = [
    { icon: IconRadar, label: 'nav_mod_monitor', path: '/project-tracking' },
    ...(FEATURES.ENABLE_AGENT_WORKSHOP ? [{ icon: IconRobot, label: 'page_title_agent_workshop', path: '/agent-workshop' }] : []),
    ...(FEATURES.ENABLE_NEOLOGISM_TRIBUNAL ? [{ icon: IconSparkles, label: 'neologism_review.title', path: '/neologism-review' }] : []),
    ...(FEATURES.ENABLE_REMIS_COPILOT ? [{ icon: IconMessageChatbot, label: 'page_title_copilot', path: '/copilot', id: 'nav-copilot' }] : []),
    { icon: IconTools, label: 'page_title_tools', path: '/tools', id: 'nav-tools' },
    ...(FEATURES.ENABLE_DOCS ? [{ icon: IconBook, label: 'page_title_docs', path: '/docs' }] : []),
];

const developmentItems = [
    { icon: IconCode, label: 'page_title_under_development', path: '/under-development' },
    { icon: IconCrane, label: 'page_title_under_construction', path: '/under-construction' },
    { icon: IconBulb, label: 'page_title_in_conception', path: '/in-conception' },
];

function NavbarLink({ icon, label, active, onClick, expanded, id, className, badge }) {
    const { t } = useTranslation();
    const LinkIcon = icon;

    return (
        <UnstyledButton
            id={id}
            onClick={onClick}
            data-active={active || undefined}
            className={`${styles.navLink} ${className || ''}`}
            title={expanded ? undefined : t(label)}
            style={{
                width: '100%',
                padding: '10px', /* equivalent to theme.spacing.xs approximately */
                display: 'flex',
                alignItems: 'center',
                justifyContent: expanded ? 'flex-start' : 'center',
            }}
        >
            <LinkIcon className={styles.icon} style={{ width: rem(22), height: rem(22) }} stroke={1.5} />
            {expanded && (
                <Text size="sm" ml="md" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'var(--font-body)' }}>
                    {t(label)}
                </Text>
            )}
            {expanded && badge > 0 && <Badge size="xs" ml="auto" variant="filled">{badge}</Badge>}
            {!expanded && badge > 0 && <span className={styles.navBadgeDot} aria-label={t('task_center.active_summary', { count: badge })} />}
        </UnstyledButton>
    );
}

function NavbarMenu({ active, expanded, icon, items, label, navigate }) {
    const { t } = useTranslation();
    return (
        <Menu position="right-start" offset={8} withinPortal shadow="md">
            <Menu.Target>
                <div>
                    <NavbarLink
                        icon={icon}
                        label={label}
                        active={active}
                        expanded={expanded}
                        className={styles.menuTrigger}
                    />
                </div>
            </Menu.Target>
            <Menu.Dropdown className={styles.navMenuDropdown} data-remis-surface="elevated">
                <Menu.Label>{t(label)}</Menu.Label>
                {items.map((item) => {
                    const ItemIcon = item.icon;
                    return (
                        <Menu.Item
                            key={item.path}
                            leftSection={<ItemIcon size={17} />}
                            rightSection={<IconChevronRight size={14} />}
                            onClick={() => navigate(item.path)}
                        >
                            {t(item.label)}
                        </Menu.Item>
                    );
                })}
            </Menu.Dropdown>
        </Menu>
    );
}

export function AppSider() {
    const navigate = useNavigate();
    const location = useLocation();
    const { startTour } = useTutorial();
    const { activeCount, attentionCount, openTaskCenter, opened: taskCenterOpened } = useTaskCenter();
    const [isPinned, setIsPinned] = useState(() => localStorage.getItem('sidebar_pinned') === 'true');
    const [hovered, setHovered] = useState(false);
    const expanded = isPinned || hovered;
    const { t } = useTranslation();

    const primaryLinks = primaryNavItems.map((link) => (
        <NavbarLink
            {...link}
            key={link.label}
            active={location.pathname === link.path}
            onClick={() => navigate(link.path)}
            expanded={expanded}
            id={link.id}
        />
    ));

    const qualityLinks = qualityNavItems.map((link) => (
        <NavbarLink
            {...link}
            key={link.label}
            active={location.pathname === link.path}
            onClick={() => navigate(link.path)}
            expanded={expanded}
        />
    ));

    const devLinks = developmentItems.map((link) => (
        <NavbarLink
            {...link}
            key={link.label}
            active={location.pathname === link.path}
            onClick={() => navigate(link.path)}
            expanded={expanded}
        />
    ));

    return (
        <Box
            id="sidebar-nav"
            className={styles.sidebarLeft}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                width: expanded ? 240 : 80,
                transition: 'width 300ms ease',
                padding: '16px', /* theme.spacing.md */
                overflowX: 'hidden',
                background: 'transparent', /* Ensure no double background */
            }}
        >
            <Stack justify="center" gap={0} mb="md" align="center" style={{ height: 60, flexShrink: 0, width: '100%' }}>
                {expanded ? (
                    <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '0 8px' }}>
                        <img
                            src="/Project Remis.png"
                            alt="Remis Logo"
                            style={{
                                height: '40px',
                                objectFit: 'contain',
                                filter: 'drop-shadow(0 0 8px rgba(0,0,0,0.3))',
                                maxWidth: '140px'
                            }}
                        />
                        <ActionIcon
                            variant="subtle"
                            color="gray"
                            onClick={() => {
                                const newVal = !isPinned;
                                setIsPinned(newVal);
                                localStorage.setItem('sidebar_pinned', String(newVal));
                            }}
                            title={isPinned ? t('sidebar.unpin') : t('sidebar.pin')}
                            style={{
                                transition: 'transform 0.2s ease',
                                transform: isPinned ? 'rotate(45deg)' : 'none',
                                color: isPinned ? 'var(--text-highlight)' : 'var(--text-muted)',
                            }}
                        >
                            {isPinned ? <IconPinFilled size={18} /> : <IconPin size={18} />}
                        </ActionIcon>
                    </Box>
                ) : (
                    <img
                        src="/Project Remis.png"
                        alt="R"
                        style={{
                            height: '32px',
                            width: '32px',
                            objectFit: 'cover',
                            objectPosition: 'center',
                            borderRadius: '4px'
                        }}
                    />
                )}
            </Stack>

            <Stack gap="xs" style={{ flex: 1 }}>
                {primaryLinks}
                <NavbarMenu
                    active={workflowItems.some((item) => location.pathname === item.path)}
                    expanded={expanded}
                    icon={IconLanguage}
                    items={workflowItems}
                    label="nav_translation_workflow"
                    navigate={navigate}
                />
                {qualityLinks}
                <NavbarLink
                    icon={IconActivity}
                    label="task_center.title"
                    active={taskCenterOpened}
                    onClick={openTaskCenter}
                    expanded={expanded}
                    badge={activeCount + attentionCount}
                />
                <NavbarMenu
                    active={moreNavItems.some((item) => location.pathname === item.path)}
                    expanded={expanded}
                    icon={IconDots}
                    items={moreNavItems}
                    label="nav_more"
                    navigate={navigate}
                />
            </Stack>

            <Stack gap="xs" mt="md" pt="md" style={{ borderTop: '1px solid var(--glass-border)' }}>
                {FEATURES.ENABLE_EXPERIMENTAL_FEATURES && devLinks}
                <NavbarLink
                    icon={IconSettings}
                    label="page_title_settings"
                    path="/settings"
                    id="nav-settings"
                    active={location.pathname === '/settings'}
                    onClick={() => navigate('/settings')}
                    expanded={expanded}
                />
                <Box id="tutorial-sidebar-link" style={{ width: '100%' }}>
                    <NavbarLink
                        icon={IconQuestionMark}
                        label="tutorial.sidebar_tutorial_btn"
                        active={false}
                        onClick={() => {
                            startTour();
                        }}
                        expanded={expanded}
                        className={styles.tutorialButton} // Add pulse animation class
                    />
                </Box>
            </Stack>
        </Box>
    );
}

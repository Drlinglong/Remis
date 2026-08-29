import React, { useState } from 'react';
import { ActionIcon, Badge, Box, Group, Menu, Stack, Text, UnstyledButton, rem } from '@mantine/core';
import {
    IconHome,
    IconBook,
    IconLanguage,
    IconVocabulary,
    IconChecklist,
    IconBriefcase,
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
    IconActivity,
    IconChevronRight,
    IconShieldCheck,
    IconTrophy,
    IconBrandSteam,
} from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import styles from './Layout.module.css';
import { FEATURES } from '../../config/features';
import {
    getNavigationSections,
    getPageById,
    isPageEnabled,
} from '../../config/pageRegistry';
import { useTutorial } from '../../context/TutorialContextCore';
import { useTaskCenter } from '../../context/TaskCenterContextCore';

const NAV_ICONS = {
    home: IconHome,
    book: IconBook,
    language: IconLanguage,
    vocabulary: IconVocabulary,
    checklist: IconChecklist,
    briefcase: IconBriefcase,
    tools: IconTools,
    settings: IconSettings,
    sparkles: IconSparkles,
    rocket: IconRocket,
    robot: IconRobot,
    radar: IconRadar,
    trophy: IconTrophy,
    'brand-steam': IconBrandSteam,
    'shield-check': IconShieldCheck,
};

const developmentItems = [
    { icon: IconCode, label: 'page_title_under_development', path: '/under-development' },
    { icon: IconCrane, label: 'page_title_under_construction', path: '/under-construction' },
    { icon: IconBulb, label: 'page_title_in_conception', path: '/in-conception' },
];

function NavbarLink({ icon, label, active, onClick, expanded, id, className, badge, nested = false }) {
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
                padding: nested ? '7px 8px 7px 24px' : '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: expanded ? 'flex-start' : 'center',
            }}
        >
            <LinkIcon
                className={styles.icon}
                style={{ width: rem(nested ? 18 : 22), height: rem(nested ? 18 : 22) }}
                stroke={1.5}
            />
            {expanded && (
                <Text size="sm" ml={nested ? 'sm' : 'md'} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'var(--font-body)' }}>
                    {t(label)}
                </Text>
            )}
            {expanded && badge > 0 && <Badge size="xs" ml="auto" variant="filled">{badge}</Badge>}
            {!expanded && badge > 0 && <span className={styles.navBadgeDot} aria-label={t('task_center.active_summary', { count: badge })} />}
        </UnstyledButton>
    );
}

function toNavigationItem(page) {
    return {
        ...page.navigation,
        icon: NAV_ICONS[page.navigation.icon],
        path: page.routePaths[0],
        match: page.match,
    };
}

function NavbarMenu({ active, expanded, icon, items, label, navigate, pathname }) {
    const { t } = useTranslation();
    const SectionIcon = icon;

    if (expanded) {
        return (
            <Box className={styles.navSection}>
                <Group
                    gap="xs"
                    className={styles.navSectionHeader}
                    data-active={active || undefined}
                >
                    <SectionIcon className={styles.icon} size={18} stroke={1.5} />
                    <Text size="xs" fw={700}>{t(label)}</Text>
                </Group>
                <Stack gap={2}>
                    {items.map((item) => (
                        <NavbarLink
                            {...item}
                            key={item.path}
                            active={item.match?.test(pathname)}
                            onClick={() => navigate(item.path)}
                            expanded
                            nested
                            className={styles.navSubLink}
                        />
                    ))}
                </Stack>
            </Box>
        );
    }

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

export function AppSider({ features = FEATURES } = {}) {
    const navigate = useNavigate();
    const location = useLocation();
    const { startTour } = useTutorial();
    const { openTaskCenter, opened: taskCenterOpened, tasks = [] } = useTaskCenter();
    const [isPinned, setIsPinned] = useState(() => localStorage.getItem('sidebar_pinned') === 'true');
    const [hovered, setHovered] = useState(false);
    const expanded = isPinned || hovered;
    const { t } = useTranslation();
    const taskQueueCount = tasks.filter((task) => (
        ['queued', 'running', 'awaiting_approval', 'failed', 'interrupted'].includes(task.status)
    )).length;
    const navigationSections = getNavigationSections(features);
    const settingsItem = toNavigationItem(getPageById('settings'));
    const documentationPage = getPageById('documentation');
    const documentationItem = isPageEnabled(documentationPage, features)
        ? toNavigationItem(documentationPage)
        : null;

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

            <Stack gap="xs" className={styles.navSections}>
                {navigationSections.map((section) => {
                    if (section.type === 'task-center') {
                        return (
                            <NavbarLink
                                key={section.id}
                                icon={IconActivity}
                                label="task_center.title"
                                active={taskCenterOpened || location.pathname === '/task-history' || location.pathname.startsWith('/tasks/')}
                                onClick={openTaskCenter}
                                expanded={expanded}
                                badge={taskQueueCount}
                            />
                        );
                    }

                    const items = section.pages.map(toNavigationItem);
                    if (section.type === 'menu') {
                        return (
                            <NavbarMenu
                                key={section.id}
                                active={section.pages.some((page) => page.match?.test(location.pathname))}
                                expanded={expanded}
                                icon={NAV_ICONS[section.icon]}
                                items={items}
                                label={section.label}
                                navigate={navigate}
                                pathname={location.pathname}
                            />
                        );
                    }

                    const item = items[0];
                    return item ? (
                        <NavbarLink
                            {...item}
                            key={section.id}
                            active={item.match?.test(location.pathname)}
                            onClick={() => navigate(item.path)}
                            expanded={expanded}
                            id={item.id}
                        />
                    ) : null;
                })}
            </Stack>

            <Stack gap="xs" mt="md" pt="md" style={{ borderTop: '1px solid var(--glass-border)' }}>
                {features.ENABLE_EXPERIMENTAL_FEATURES && devLinks}
                {documentationItem && (
                    <NavbarLink
                        {...documentationItem}
                        active={documentationItem.match?.test(location.pathname)}
                        onClick={() => navigate(documentationItem.path)}
                        expanded={expanded}
                    />
                )}
                <NavbarLink
                    {...settingsItem}
                    id="nav-settings"
                    active={settingsItem.match?.test(location.pathname)}
                    onClick={() => navigate(settingsItem.path)}
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

import React, { useState } from 'react';
import { Stack, UnstyledButton, rem, Text, Box, ActionIcon } from '@mantine/core';
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
    IconPin,
    IconPinFilled,
} from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import styles from './Layout.module.css';
import { FEATURES } from '../../config/features';
import { useTutorial } from '../../context/TutorialContext';
import ThemeContext from '../../ThemeContext';

// Navigation items configuration
const navItems = [
    { icon: IconHome, label: 'page_title_home', path: '/' },
    { icon: IconBriefcase, label: 'page_title_project_management', path: '/project-management' },
    { icon: IconLanguage, label: 'page_title_translation', path: '/translation' },
    ...(FEATURES.ENABLE_INCREMENTAL_TRANSLATION ? [{ icon: IconRocket, label: 'incremental_translation.title', path: '/incremental-translation' }] : []),
    { icon: IconVocabulary, label: 'page_title_glossary_manager', path: '/glossary-manager' },
    { icon: IconChecklist, label: 'page_title_proofreading', path: '/proofreading' },
    ...(FEATURES.ENABLE_AGENT_WORKSHOP ? [{ icon: IconRobot, label: 'page_title_agent_workshop', path: '/agent-workshop' }] : []),
    // Conditionally include Neologism Tribunal
    ...(FEATURES.ENABLE_NEOLOGISM_TRIBUNAL ? [{ icon: IconSparkles, label: 'neologism_review.title', path: '/neologism-review' }] : []),
    { icon: IconTools, label: 'page_title_tools', path: '/tools', id: 'nav-tools' },
    ...(FEATURES.ENABLE_DOCS ? [{ icon: IconBook, label: 'page_title_docs', path: '/docs' }] : []),
    { icon: IconSettings, label: 'page_title_settings', path: '/settings', id: 'nav-settings' },
];

const developmentItems = [
    { icon: IconCode, label: 'page_title_under_development', path: '/under-development' },
    { icon: IconCrane, label: 'page_title_under_construction', path: '/under-construction' },
    { icon: IconBulb, label: 'page_title_in_conception', path: '/in-conception' },
];

function NavbarLink({ icon: Icon, label, active, onClick, expanded, id, className }) {
    const { t } = useTranslation();
    const { theme } = React.useContext(ThemeContext);

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
            <Icon className={styles.icon} style={{ width: rem(22), height: rem(22) }} stroke={1.5} />
            {expanded && (
                <Text size="sm" ml="md" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'var(--font-body)' }}>
                    {t(label)}
                </Text>
            )}
        </UnstyledButton>
    );
}

export function AppSider() {
    const navigate = useNavigate();
    const location = useLocation();
    const { startTour } = useTutorial();
    const [isPinned, setIsPinned] = useState(() => localStorage.getItem('sidebar_pinned') === 'true');
    const [hovered, setHovered] = useState(false);
    const expanded = isPinned || hovered;
    const { t } = useTranslation();

    const links = navItems.map((link) => (
        <NavbarLink
            {...link}
            key={link.label}
            active={location.pathname === link.path}
            onClick={() => navigate(link.path)}
            expanded={expanded}
            id={link.id}
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
                {links}
            </Stack>

            <Stack gap="xs" mt="md" pt="md" style={{ borderTop: '1px solid var(--glass-border)' }}>
                {FEATURES.ENABLE_EXPERIMENTAL_FEATURES && devLinks}
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

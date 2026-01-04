import React, { useState } from 'react';
import { Stack, Tooltip, UnstyledButton, rem, Text, Box } from '@mantine/core';
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
    { icon: IconVocabulary, label: 'page_title_glossary_manager', path: '/glossary-manager' },
    { icon: IconChecklist, label: 'page_title_proofreading', path: '/proofreading' },
    // Conditionally include Neologism Tribunal
    ...(FEATURES.ENABLE_NEOLOGISM_TRIBUNAL ? [{ icon: IconSparkles, label: 'neologism_review.title', path: '/neologism-review' }] : []),
    { icon: IconTools, label: 'page_title_tools', path: '/tools', id: 'nav-tools' },
    // { icon: IconBook, label: 'page_title_docs', path: '/docs' },
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
        <Tooltip label={t(label)} position="right" transitionProps={{ duration: 0 }} disabled={expanded}>
            <UnstyledButton
                id={id}
                onClick={onClick}
                data-active={active || undefined}
                className={`${styles.navLink} ${className || ''}`}
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
        </Tooltip>
    );
}

export function AppSider() {
    const navigate = useNavigate();
    const location = useLocation();
    const { startTour } = useTutorial();
    const [expanded, setExpanded] = useState(false);

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
            onMouseEnter={() => setExpanded(true)}
            onMouseLeave={() => setExpanded(false)}
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
            <Stack justify="center" gap={0} mb="md" align="center" style={{ height: 60, flexShrink: 0 }}>
                {expanded ? (
                    <img
                        src="/Project Remis.png"
                        alt="Remis Logo"
                        style={{
                            height: '40px',
                            objectFit: 'contain',
                            filter: 'drop-shadow(0 0 8px rgba(0,0,0,0.3))'
                        }}
                    />
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
                {devLinks}
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

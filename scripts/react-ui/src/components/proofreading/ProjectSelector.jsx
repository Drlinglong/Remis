import React, { useState, useMemo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Select,
    Group,
    Box
} from '@mantine/core';
import { IconSearch, IconFilter } from '@tabler/icons-react';

/**
 * Project Selection Component
 * 
 * Features:
 * - Game Filter: Dynamically extracted from project list
 * - Searchable Project Select: Direct access to projects
 * - Glassmorphism Aesthetic
 */
const ProjectSelector = ({
    projects = [],
    selectedProject,
    onProjectSelect
}) => {
    const { t } = useTranslation();
    const [gameFilter, setGameFilter] = useState('ALL');

    // 1. Dynamic Game List Extraction
    const gameOptions = useMemo(() => {
        const games = new Set(projects.map(p => p.game_id).filter(Boolean));
        return ['ALL', ...Array.from(games)].map(game => ({
            value: game,
            label: game === 'ALL' ? t('common.all_games') : game.toUpperCase()
        }));
    }, [projects, t]);

    // 2. Filter Projects based on Game
    const filteredProjects = useMemo(() => {
        if (gameFilter === 'ALL') return projects;
        return projects.filter(p => p.game_id === gameFilter);
    }, [projects, gameFilter]);

    // 3. Project Select Options
    const projectOptions = useMemo(() => {
        if (!filteredProjects) return [];
        return filteredProjects.map(p => ({
            value: p.project_id,
            label: p.name
            // NOTE: Do NOT use 'group' property here for flat lists, it causes Mantine to crash expecting 'items'.
        }));
    }, [filteredProjects]);

    // Cleanup: Reset filter if selected project changes externally and doesn't match? 
    // Actually, we probably don't need to force reset, but let's ensure the selector shows the right specific value.

    return (
        <Group gap="xs" wrap="nowrap" align="center">
            {/* Game Filter */}
            <Select
                placeholder={t('common.filter_game')}
                data={gameOptions}
                value={gameFilter}
                onChange={setGameFilter}
                variant="filled"
                size="xs"
                style={{ width: 110 }}
                leftSection={<IconFilter size={14} style={{ opacity: 0.6 }} />}
                styles={{
                    input: {
                        backgroundColor: 'rgba(0, 0, 0, 0.2)',
                        backdropFilter: 'blur(5px)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: 'var(--mantine-color-text)',
                        '&:focus': {
                            borderColor: 'var(--mantine-color-blue-filled)',
                        }
                    }
                }}
            />

            {/* Project Search & Select */}
            <Select
                placeholder={t('proofreading.select_project_placeholder')}
                data={projectOptions}
                value={selectedProject?.project_id || null}
                onChange={onProjectSelect}
                searchable
                nothingFoundMessage={t('common.nothing_found')}
                variant="filled"
                size="xs"
                style={{ minWidth: 240, flex: 1 }}
                leftSection={<IconSearch size={14} style={{ opacity: 0.6 }} />}
                styles={{
                    input: {
                        backgroundColor: 'rgba(0, 0, 0, 0.2)',
                        backdropFilter: 'blur(5px)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: 'var(--mantine-color-text)',
                        fontWeight: 500,
                        '&:focus': {
                            borderColor: 'var(--mantine-color-blue-filled)',
                        }
                    },
                    dropdown: {
                        backgroundColor: 'rgba(30, 30, 30, 0.95)',
                        backdropFilter: 'blur(10px)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                    }
                }}
            />
        </Group>
    );
};

export default ProjectSelector;

import React, { useMemo } from 'react';
import { Paper, Group, TextInput, Select, SimpleGrid, Card, Stack, Box, Title, Text, Badge } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import styles from '../../pages/Translation.module.css';

export const ProjectSelectStep = ({
    projects,
    searchQuery,
    setSearchQuery,
    gameFilter,
    setGameFilter,
    selectedProject,
    onSelectProject,
}) => {
    const { t } = useTranslation();

    const filteredProjects = useMemo(() => {
        const normalizedQuery = searchQuery.trim().toLowerCase();
        return projects.filter((project) => {
            const matchesGame = gameFilter === 'all' || project.game_id === gameFilter;
            const haystack = [
                project.name,
                project.game_id,
                project.source_language,
                project.source_path,
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            const matchesQuery = !normalizedQuery || haystack.includes(normalizedQuery);
            return matchesGame && matchesQuery;
        });
    }, [gameFilter, projects, searchQuery]);

    const gameFilterOptions = useMemo(() => {
        const games = Array.from(new Set(projects.map((project) => project.game_id).filter(Boolean)));
        return [
            { value: 'all', label: t('common.all_games', { defaultValue: 'All Games' }) },
            ...games.map((game) => ({ value: game, label: game.toUpperCase() })),
        ];
    }, [projects, t]);

    return (
        <Stack mt="xl" className={styles.executionStep}>
            <Paper id="incremental-project-selector" withBorder p="md" radius="md" className={styles.glassCard}>
                <Group grow align="flex-end">
                    <TextInput
                        label={t('common.search', { defaultValue: 'Search' })}
                        placeholder={t('incremental_translation.project_search_placeholder')}
                        value={searchQuery}
                        onChange={(event) => setSearchQuery(event.currentTarget.value)}
                        leftSection={<IconSearch size={16} />}
                    />
                    <Select
                        label={t('common.filter_game')}
                        data={gameFilterOptions}
                        value={gameFilter}
                        onChange={(value) => setGameFilter(value || 'all')}
                    />
                </Group>
            </Paper>

            <SimpleGrid id="incremental-project-grid" cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
                {filteredProjects.map((p) => (
                    <Card
                        key={p.project_id}
                        padding="lg"
                        radius="md"
                        withBorder
                        onClick={() => onSelectProject(p)}
                        style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                        className={selectedProject?.project_id === p.project_id ? styles.selectedCard : styles.glassCard}
                    >
                        <Stack gap="xs">
                            <Box>
                                <Title order={5}>{p.name}</Title>
                                <Text size="xs" c="dimmed">
                                    {t('incremental_translation.project_folder')}: {p.source_path?.split(/[\\/]/).pop()}
                                </Text>
                            </Box>
                            <Group gap="xs">
                                <Badge color="blue" variant="light">
                                    {t('incremental_translation.project_game')}: {p.game_id}
                                </Badge>
                                <Badge color="teal" variant="light">
                                    {t('incremental_translation.project_source_language')}: {p.source_language}
                                </Badge>
                            </Group>
                            <Text size="xs" c="dimmed" lineClamp={2}>{p.source_path}</Text>
                        </Stack>
                    </Card>
                ))}
            </SimpleGrid>

            {filteredProjects.length === 0 && (
                <Paper withBorder p="xl" radius="md" className={styles.glassCard}>
                    <Text ta="center" c="dimmed">
                        {t('common.nothing_found')}
                    </Text>
                </Paper>
            )}
        </Stack>
    );
};

export default ProjectSelectStep;

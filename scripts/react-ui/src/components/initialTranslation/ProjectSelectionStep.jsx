import React from 'react';
import {
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Stack,
  Text,
  TextInput,
  Title,
  Box,
} from '@mantine/core';
import { IconFolderOpen, IconSearch } from '@tabler/icons-react';

import layoutStyles from '../layout/Layout.module.css';
import { resolveGameName } from '../../utils/initialTranslation';

export default function ProjectSelectionStep({
  config,
  filteredProjects,
  gameFilter,
  navigate,
  onProjectSelect,
  projects,
  searchQuery,
  selectedProjectId,
  setGameFilter,
  setSearchQuery,
  t,
}) {
  return (
    <Container fluid px="xl" id="translation-project-list" style={{ maxWidth: '100%', width: '100%' }}>
      <Stack gap="lg">
        <Title order={2} ta="center" mb="lg" style={{ letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--mantine-color-blue-4)' }}>
          {t('translation_page.subtitle')}
        </Title>

        {projects.length > 0 ? (
          <>
            <Group mb="md" grow>
              <TextInput
                placeholder={t('translation_page.search_placeholder')}
                leftSection={<IconSearch size={16} />}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.currentTarget.value)}
                variant="filled"
                radius="md"
              />
              <Box>
                <Text size="sm" mb={6} c="dimmed">
                  {t('translation_page.filter_game_placeholder')}
                </Text>
                <select
                  value={gameFilter}
                  onChange={(event) => setGameFilter(event.currentTarget.value || 'all')}
                  style={{
                    width: '100%',
                    minHeight: 36,
                    padding: '8px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--mantine-color-dark-4)',
                    background: 'rgba(255, 255, 255, 0.06)',
                    color: 'var(--mantine-color-text)',
                    outline: 'none',
                  }}
                >
                  <option value="all">{t('common.all_games')}</option>
                  {Object.values(config.game_profiles).map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name.split('(')[0].trim()}
                    </option>
                  ))}
                </select>
              </Box>
            </Group>

            <Card p="sm" radius="md" mb="xs" bg="rgba(0, 0, 0, 0.3)" withBorder style={{ borderColor: 'var(--mantine-color-dark-4)' }}>
              <Group>
                <Text fw={700} size="sm" c="dimmed" style={{ width: '150px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  {t('translation_page.table_header.game')}
                </Text>
                <Text fw={700} size="sm" c="dimmed" style={{ flex: 1, textTransform: 'uppercase', letterSpacing: '1px' }}>
                  {t('translation_page.table_header.mod_name')}
                </Text>
                <Text fw={700} size="sm" c="dimmed" style={{ width: '80px', textAlign: 'right', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  {t('translation_page.table_header.action')}
                </Text>
              </Group>
            </Card>

            <div style={{ maxHeight: 600, overflowY: 'auto', overflowX: 'hidden' }}>
              <Stack gap="xs">
                {filteredProjects.map((project) => {
                  const gameName = resolveGameName(config.game_profiles, project.game_id);

                  return (
                    <Card
                      key={project.value}
                      p="md"
                      radius="md"
                      withBorder
                      className={layoutStyles.glassCard}
                      style={{
                        cursor: 'pointer',
                        borderColor: selectedProjectId === project.value ? 'var(--mantine-color-blue-6)' : 'transparent',
                        backgroundColor: selectedProjectId === project.value ? 'rgba(34, 139, 230, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                        transition: 'all 0.2s ease',
                        '&:hover': {
                          backgroundColor: 'rgba(255, 255, 255, 0.05)',
                          transform: 'translateX(5px)',
                        },
                      }}
                      onClick={() => onProjectSelect(project.value)}
                    >
                      <Group>
                        <Badge
                          color={project.game_id === 'victoria3' ? 'pink' : 'blue'}
                          variant="filled"
                          w={150}
                          radius="sm"
                        >
                          {gameName}
                        </Badge>
                        <Text fw={500} size="lg" style={{ flex: 1 }}>
                          {project.label}
                        </Text>
                        <Button
                          size="sm"
                          variant={selectedProjectId === project.value ? 'filled' : 'subtle'}
                          color="blue"
                          onClick={(event) => {
                            event.stopPropagation();
                            onProjectSelect(project.value);
                          }}
                        >
                          {selectedProjectId === project.value ? t('translation_page.button.selected') : t('translation_page.button.select')}
                        </Button>
                      </Group>
                    </Card>
                  );
                })}
                {projects.length === 0 && (
                  <Text c="dimmed" ta="center" py="xl">{t('translation_page.no_projects_found')}</Text>
                )}
              </Stack>
            </div>
          </>
        ) : (
          <Center p="xl">
            <Stack align="center">
              <IconFolderOpen size={48} stroke={1.5} color="var(--mantine-color-gray-5)" />
              <Text c="dimmed">{t('translation_page.no_projects_action')}</Text>
              <Button variant="subtle" onClick={() => navigate('/')}>{t('translation_page.go_to_project_management')}</Button>
            </Stack>
          </Center>
        )}
      </Stack>
    </Container>
  );
}

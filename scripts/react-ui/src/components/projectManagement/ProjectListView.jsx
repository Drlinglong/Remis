import React from 'react';
import {
  BackgroundImage,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Group,
  Input,
  Overlay,
  SimpleGrid,
  Text,
  Title,
} from '@mantine/core';
import {
  IconArchive,
  IconArrowLeft,
  IconPlus,
  IconSearch,
} from '@tabler/icons-react';

import heroBg from '../../assets/project_hero_bg.png';
import styles from '../../pages/ProjectManagement.module.css';
import { getGameBadgeColor } from '../../utils/gamePresentation';

export function ProjectListView({
  projects,
  searchQuery,
  setIsCreateModalOpen,
  setSearchQuery,
  setSelectedProjectId,
  setViewMode,
  t,
  viewMode,
}) {
  const filteredProjects = projects.filter((project) => (
    project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    project.game_id.toLowerCase().includes(searchQuery.toLowerCase())
  ));

  return (
    <div id="project-list-container" style={{ minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box className={styles.heroSection}>
        <BackgroundImage src={heroBg} radius="md" style={{ height: '100%' }}>
          <Overlay color="#000" opacity={0.6} zIndex={1} radius="md" />
          <Center p="md" style={{ height: '100%', position: 'relative', zIndex: 2, flexDirection: 'column' }}>
            <Title order={1} className={styles.heroTitle}>
              {viewMode === 'active' ? t('page_title_project_management') : t('project_management.archives_title')}
            </Title>
            <Text size="lg" mt="sm" className={styles.heroSubtitle}>
              {viewMode === 'active' ? t('project_management.hero_desc') : t('project_management.actions.archives_desc')}
            </Text>

            <Group mt="lg" className={styles.heroControls}>
              {viewMode === 'archives' && (
                <Button variant="outline" color="gray" leftSection={<IconArrowLeft />} onClick={() => setViewMode('active')}>
                  {t('button_back')}
                </Button>
              )}
              <Input
                icon={<IconSearch size={16} />}
                placeholder={t('translation_page.search_placeholder')}
                radius="xl"
                size="md"
                className={styles.heroSearch}
                classNames={{ input: styles.heroSearchInput }}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.currentTarget.value)}
              />
            </Group>
          </Center>
        </BackgroundImage>
      </Box>

      <Box className={styles.projectContent}>
        {viewMode === 'active' && (
          <Box className={styles.actionsSection} data-remis-surface="surface">
            <Box>
              <Title order={3}>
                {t('project_management.file_list.table.actions')}
              </Title>
              <Text size="sm" c="dimmed" mt={4}>
                {t('project_management.actions.create_new_desc')}
              </Text>
            </Box>
            <Group className={styles.actionToolbar}>
              <Button
                id="create-project-btn"
                leftSection={<IconPlus size={18} />}
                onClick={() => setIsCreateModalOpen(true)}
              >
                {t('project_management.actions.create_new')}
              </Button>

              <Button
                variant="subtle"
                color="gray"
                leftSection={<IconArchive size={18} />}
                onClick={() => setViewMode('archives')}
              >
                {t('project_management.actions.archives')}
              </Button>
            </Group>
          </Box>
        )}

        <Title order={3} mt="xl" mb="md">
          {viewMode === 'active' ? t('page_title_project_management') : t('project_management.archives_title')}
          <Badge ml="md" size="lg" variant="outline">
            {filteredProjects.length}
          </Badge>
        </Title>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} gap="lg">
          {filteredProjects.map((project) => (
            <Card
              key={project.project_id}
              padding="lg"
              radius="md"
              onClick={() => setSelectedProjectId(project.project_id)}
              className={styles.projectCard}
              data-remis-surface="surface"
            >
              <Group justify="space-between" mb="xs">
                <Text fw={500} className={styles.projectTitle}>{project.name}</Text>
                <Badge
                  color={getGameBadgeColor(project.game_id)}
                  data-game-color={getGameBadgeColor(project.game_id)}
                  variant="filled"
                >
                  {project.game_id}
                </Badge>
              </Group>
              <Text size="sm" color="dimmed" lineClamp={2}>
                {project.notes || t('project_management.no_notes', 'No notes')}
              </Text>
              <Group mt="md">
                <Text size="xs" color="dimmed">
                  {t('project_management.last_updated', 'Last updated')}: {new Date(project.last_updated || Date.now()).toLocaleDateString()}
                </Text>
              </Group>
            </Card>
          ))}
        </SimpleGrid>
      </Box>
    </div>
  );
}

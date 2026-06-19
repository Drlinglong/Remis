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
import { IconArrowLeft, IconSearch } from '@tabler/icons-react';

import cardNewProject from '../../assets/card_new_project.png';
import cardOpenProject from '../../assets/card_open_project.png';
import heroBg from '../../assets/project_hero_bg.png';
import styles from '../../pages/ProjectManagement.module.css';

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
      <Box style={{ height: '300px', position: 'relative', flexShrink: 0 }}>
        <BackgroundImage src={heroBg} radius="md" style={{ height: '100%' }}>
          <Overlay color="#000" opacity={0.6} zIndex={1} radius="md" />
          <Center p="md" style={{ height: '100%', position: 'relative', zIndex: 2, flexDirection: 'column' }}>
            <Title order={1} className={styles.heroTitle}>
              {viewMode === 'active' ? t('page_title_project_management') : t('project_management.archives_title')}
            </Title>
            <Text size="lg" mt="sm" className={styles.heroSubtitle}>
              {viewMode === 'active' ? t('project_management.hero_desc') : t('project_management.actions.archives_desc')}
            </Text>

            <Group mt="xl">
              {viewMode === 'archives' && (
                <Button variant="outline" color="gray" leftSection={<IconArrowLeft />} onClick={() => setViewMode('active')}>
                  {t('button_back')}
                </Button>
              )}
              <Input
                icon={<IconSearch size={16} />}
                placeholder="Search projects..."
                radius="xl"
                size="md"
                style={{ width: '400px' }}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.currentTarget.value)}
                styles={{ input: { background: 'rgba(255,255,255,0.1)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)' } }}
              />
            </Group>
          </Center>
        </BackgroundImage>
      </Box>

      <Box style={{ flex: 1, padding: '20px' }}>
        {viewMode === 'active' && (
          <>
            <Title order={3} mb="md">Actions</Title>
            <SimpleGrid cols={3} gap="lg" breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>
              <Card
                id="create-project-btn"
                padding="lg"
                radius="md"
                className={styles.actionCard}
                onClick={() => setIsCreateModalOpen(true)}
              >
                <Card.Section>
                  <BackgroundImage src={cardNewProject} style={{ height: 140 }} />
                </Card.Section>
                <Group justify="space-between" mt="md" mb="xs">
                  <Text fw={500}>{t('project_management.actions.create_new')}</Text>
                  <Badge color="pink" variant="light">New</Badge>
                </Group>
                <Text size="sm" color="dimmed">
                  {t('project_management.actions.create_new_desc')}
                </Text>
              </Card>

              <Card
                padding="lg"
                radius="md"
                className={styles.actionCard}
                onClick={() => setViewMode('archives')}
              >
                <Card.Section>
                  <BackgroundImage src={cardOpenProject} style={{ height: 140 }} />
                </Card.Section>
                <Group justify="space-between" mt="md" mb="xs">
                  <Text fw={500}>{t('project_management.actions.archives')}</Text>
                  <Badge color="gray" variant="light">View</Badge>
                </Group>
                <Text size="sm" color="dimmed">
                  {t('project_management.actions.archives_desc')}
                </Text>
              </Card>
            </SimpleGrid>
          </>
        )}

        <Title order={3} mt="xl" mb="md">
          {viewMode === 'active' ? t('page_title_project_management') : t('project_management.archives_title')}
          <Badge ml="md" size="lg" variant="outline">
            {filteredProjects.length}
          </Badge>
        </Title>

        <SimpleGrid cols={3} gap="lg" breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>
          {filteredProjects.map((project) => (
            <Card
              key={project.project_id}
              padding="lg"
              radius="md"
              onClick={() => setSelectedProjectId(project.project_id)}
              className={styles.projectCard}
            >
              <Group justify="space-between" mb="xs">
                <Text fw={500} className={styles.projectTitle}>{project.name}</Text>
                <Badge color={project.status === 'active' ? 'blue' : 'gray'}>{project.game_id}</Badge>
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

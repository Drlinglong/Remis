import React from 'react';
import {
  Badge,
  Box,
  Button,
  Card,
  Group,
  Input,
  Text,
  Title,
} from '@mantine/core';
import {
  IconArchive,
  IconArrowLeft,
  IconArrowRight,
  IconFolderOff,
  IconPlus,
  IconSearch,
} from '@tabler/icons-react';

import styles from './ProjectListView.module.css';
import { getGameBadgeColor } from '../../utils/gamePresentation';
import { formatCurrentLocalizedDateTime } from '../../utils/localizedDateTime';

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
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredProjects = projects.filter((project) => (
    String(project.name || '').toLowerCase().includes(normalizedQuery)
    || String(project.game_id || '').toLowerCase().includes(normalizedQuery)
  ));
  const isArchive = viewMode === 'archives';

  return (
    <div id="project-list-container" className={styles.page} data-remis-surface="canvas">
      <header className={styles.workspaceHeader}>
        <Box className={styles.orientationCopy}>
          <Text className={styles.kicker}>
            {t('project_management.workspace_label', 'Project library')}
          </Text>
          <Group gap="sm" align="center" wrap="wrap">
            <Title order={1} className={styles.pageTitle}>
              {isArchive ? t('project_management.archives_title') : t('page_title_project_management')}
            </Title>
            <Badge size="lg" variant="outline">{projects.length}</Badge>
          </Group>
          <Text className={styles.pageDescription}>
            {isArchive
              ? t('project_management.actions.archives_desc')
              : t('project_management.hero_desc')}
          </Text>
        </Box>

        <Group className={styles.headerActions} align="center" wrap="wrap">
          {!isArchive && (
            <Button
              id="create-project-btn"
              data-remis-action="primary"
              leftSection={<IconPlus size={18} />}
              onClick={() => setIsCreateModalOpen(true)}
            >
              {t('project_management.actions.create_new')}
            </Button>
          )}
          <Button
            variant="default"
            leftSection={isArchive ? <IconArrowLeft size={18} /> : <IconArchive size={18} />}
            onClick={() => setViewMode(isArchive ? 'active' : 'archives')}
          >
            {isArchive ? t('button_back') : t('project_management.actions.archives')}
          </Button>
        </Group>
      </header>

      <section className={styles.projectContent} aria-labelledby="project-list-heading">
        <div className={styles.listToolbar}>
          <Box>
            <Text className={styles.sectionLabel}>
              {isArchive
                ? t('project_management.archived_projects', 'Archived projects')
                : t('project_management.active_projects', 'Active projects')}
            </Text>
            <Title id="project-list-heading" order={2} className={styles.sectionTitle}>
              {t('project_management.project_count', '{{count}} projects', { count: filteredProjects.length })}
            </Title>
          </Box>
          <Input
            leftSection={<IconSearch size={16} />}
            placeholder={t('translation_page.search_placeholder')}
            size="md"
            className={styles.search}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.currentTarget.value)}
          />
        </div>

        {filteredProjects.length > 0 ? (
          <div className={styles.projectGrid}>
            {filteredProjects.map((project) => (
              <Card
                component="button"
                type="button"
                key={project.project_id}
                padding="lg"
                onClick={() => setSelectedProjectId(project.project_id)}
                className={styles.projectCard}
                data-remis-surface="surface"
                aria-label={t('project_management.open_project', 'Open {{name}}', { name: project.name })}
              >
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Box className={styles.projectIdentity}>
                    <Text className={styles.projectTitle}>{project.name}</Text>
                    <Text size="sm" className={styles.projectNotes} lineClamp={2}>
                      {project.notes || t('project_management.no_notes', 'No notes')}
                    </Text>
                  </Box>
                  <IconArrowRight className={styles.openIcon} size={20} aria-hidden="true" />
                </Group>

                <Group className={styles.projectMeta} justify="space-between" align="center" wrap="wrap">
                  <Group gap="xs">
                    <Badge
                      color={getGameBadgeColor(project.game_id)}
                      data-game-color={getGameBadgeColor(project.game_id)}
                      variant="filled"
                    >
                      {project.game_id}
                    </Badge>
                    <Badge variant="outline">
                      {t(`project_management.status.${project.status}`, project.status)}
                    </Badge>
                  </Group>
                  <Text size="xs" className={styles.updatedAt}>
                    {t('project_management.last_updated', 'Last updated')}: {' '}
                    {formatCurrentLocalizedDateTime(project.last_updated || Date.now(), { dateStyle: 'short' })}
                  </Text>
                </Group>
              </Card>
            ))}
          </div>
        ) : (
          <Box className={styles.emptyState} data-remis-surface="surface">
            <IconFolderOff size={32} aria-hidden="true" />
            <Title order={3}>
              {normalizedQuery
                ? t('project_management.no_search_results', 'No matching projects')
                : t('project_management.no_projects', 'No projects here yet')}
            </Title>
            <Text size="sm">
              {normalizedQuery
                ? t('project_management.no_search_results_hint', 'Try a project name or game identifier.')
                : t('project_management.no_projects_hint', 'Create a project from a local mod folder to begin.')}
            </Text>
          </Box>
        )}
      </section>
    </div>
  );
}

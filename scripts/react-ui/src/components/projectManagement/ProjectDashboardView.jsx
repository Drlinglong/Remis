import React, { useEffect, useRef } from 'react';
import { Badge, Button, Group, Tabs, Text, Title } from '@mantine/core';
import {
  IconArrowLeft,
  IconBrandSteam,
  IconChecklist,
  IconClock,
  IconLayoutDashboard,
  IconLayoutKanban,
  IconVocabulary,
} from '@tabler/icons-react';

import { FEATURES } from '../../config/features';
import ProjectGlossaryPanel from '../project/ProjectGlossaryPanel';
import ProjectHeader from '../project/ProjectHeader';
import ProjectHistory from '../project/ProjectHistory';
import ProjectValidation from '../project/ProjectValidation';
import KanbanBoard from '../tools/KanbanBoard';
import ProjectOverview from '../tools/ProjectOverview';
import SteamWorkshopOverview from '../steamWorkshop/SteamWorkshopOverview';
import styles from './ProjectDashboardView.module.css';

export function ProjectDashboardView({
  activeTab,
  fetchProjectFiles,
  fetchProjects,
  handleFileStatusChange,
  handleOpenManage,
  handleProofread,
  handleRefreshFiles,
  handleRepairMetadata,
  handleUpdateNotes,
  handleUpdateStatus,
  metadataRepairLoading,
  projectDataRefreshToken,
  projectDetails,
  selectedProject,
  setActiveTab,
  setDeleteModalOpen,
  setProjectDataRefreshToken,
  setSelectedProjectId,
  t,
}) {
  const previousTabRef = useRef(activeTab);

  useEffect(() => {
    const previousTab = previousTabRef.current;
    previousTabRef.current = activeTab;

    if (activeTab === 'overview' && previousTab !== 'overview') {
      fetchProjectFiles(selectedProject.project_id);
    }
  }, [activeTab, fetchProjectFiles, selectedProject.project_id]);

  return (
    <div data-remis-surface="canvas" className={styles.projectCanvas}>
      <header id="project-dashboard-header" className={styles.identityBar}>
        <Button
          variant="subtle"
          className={styles.backButton}
          onClick={() => setSelectedProjectId(null)}
          leftSection={<IconArrowLeft size={16} />}
        >
          {t('button_back')}
        </Button>
        <div className={styles.projectIdentity}>
          <Text className={styles.kicker}>{t('project_management.current_project', 'Current project')}</Text>
          <Group gap="sm" align="center" wrap="wrap">
            <Title order={1} className={styles.projectTitle}>{selectedProject.name}</Title>
            <Badge className={styles.statusBadge} data-status={selectedProject.status} variant="outline">
              {t(`project_management.status.${selectedProject.status}`, selectedProject.status)}
            </Badge>
          </Group>
          <Group gap="xs" className={styles.identityMeta} wrap="wrap">
            <Text size="sm">{selectedProject.game_id}</Text>
            <span aria-hidden="true">•</span>
            <Text size="sm">
              {t('project_management.source_language', 'Source language')}: {' '}
              {projectDetails?.source_language || selectedProject.source_language || t('common.unknown', 'Unknown')}
            </Text>
          </Group>
        </div>
      </header>

      {projectDetails ? (
        <ProjectHeader
          projectDetails={projectDetails}
          handleStatusChange={handleUpdateStatus}
          onDeleteForever={() => setDeleteModalOpen(true)}
          onManageProject={handleOpenManage}
          onRefresh={handleRefreshFiles}
          onRepairMetadata={handleRepairMetadata}
          repairingMetadata={metadataRepairLoading}
        />
      ) : (
        <div className={styles.headerLoading} data-remis-surface="surface" role="status">
          <Text>{t('project_management.loading_details', 'Loading project details…')}</Text>
        </div>
      )}

      <Tabs
        value={activeTab}
        onChange={setActiveTab}
        keepMounted={false}
        variant="default"
        classNames={{ root: styles.tabsRoot, list: styles.tabsList, panel: styles.tabsPanel }}
      >
        <Tabs.List id="project-dashboard-tabs" aria-label={t('project_management.workspace_navigation', 'Project workspace navigation')}>
          <Text component="span" className={styles.navLabel}>{t('project_management.main_flow', 'Main flow')}</Text>
          <Tabs.Tab value="overview" leftSection={<IconLayoutDashboard size={16} />}>
            {t('project_management.tabs_overview')}
          </Tabs.Tab>
          <Tabs.Tab value="validation" id="validation-tab-control" leftSection={<IconChecklist size={16} />}>
            {t('project_management.tabs_validation')}
            {Number(projectDetails?.validation?.issues_count || 0) > 0 && (
              <Badge size="xs" ml="xs" variant="filled" color="red">
                {projectDetails.validation.issues_count}
              </Badge>
            )}
          </Tabs.Tab>
          {FEATURES.ENABLE_PROJECT_HISTORY && (
            <Tabs.Tab value="history" id="history-tab-control" leftSection={<IconClock size={16} />}>
              {t('project_management.tabs_history', 'Project History')}
            </Tabs.Tab>
          )}
          <span className={styles.navSeparator} aria-hidden="true" />
          <Text component="span" className={styles.navLabel}>{t('project_management.project_tools', 'Project tools')}</Text>
          <Tabs.Tab value="project_glossary" leftSection={<IconVocabulary size={16} />}>
            {t('project_management.tabs_project_glossary')}
          </Tabs.Tab>
          <Tabs.Tab value="taskboard" leftSection={<IconLayoutKanban size={16} />}>
            {t('project_management.tabs_kanban')}
          </Tabs.Tab>
          <Tabs.Tab value="publishing_assets" leftSection={<IconBrandSteam size={16} />}>
            {t('project_management.tabs_publishing_assets', '发布素材管理')}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel id="project-dashboard-overview" value="overview" className={styles.scrollPanel}>
          {projectDetails ? (
            <ProjectOverview
              projectDetails={projectDetails}
              handleProofread={handleProofread}
              onFileStatusChange={handleFileStatusChange}
              handleNotesChange={handleUpdateNotes}
              onPathsUpdated={() => fetchProjectFiles(selectedProject.project_id)}
            />
          ) : <Text>{t('project_management.loading_details', 'Loading project details…')}</Text>}
        </Tabs.Panel>

        <Tabs.Panel value="taskboard" className={`${styles.scrollPanel} ${styles.kanbanPanel}`}>
          <KanbanBoard projectId={selectedProject.project_id} key={selectedProject.project_id + (projectDetails?.refreshKey || '')} />
        </Tabs.Panel>

        <Tabs.Panel value="project_glossary" className={styles.scrollPanel}>
          <ProjectGlossaryPanel project={selectedProject} t={t} />
        </Tabs.Panel>

        <Tabs.Panel value="publishing_assets" className={styles.scrollPanel}>
          <SteamWorkshopOverview projectId={selectedProject.project_id} projectName={selectedProject.name} />
        </Tabs.Panel>

        <Tabs.Panel value="validation" className={styles.scrollPanel}>
          <ProjectValidation projectId={selectedProject.project_id} />
        </Tabs.Panel>

        {FEATURES.ENABLE_PROJECT_HISTORY && (
          <Tabs.Panel value="history" className={styles.scrollPanel}>
            <ProjectHistory
              projectId={selectedProject.project_id}
              projectDetails={projectDetails}
              refreshToken={projectDataRefreshToken}
              onProjectDataChanged={() => {
                const refreshPromise = Promise.all([
                  fetchProjects(),
                  fetchProjectFiles(selectedProject.project_id),
                ]);
                setProjectDataRefreshToken((prev) => prev + 1);
                return refreshPromise;
              }}
            />
          </Tabs.Panel>
        )}
      </Tabs>
    </div>
  );
}

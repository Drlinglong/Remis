import React, { useEffect, useRef } from 'react';
import { Badge, Button, Group, Menu, Paper, Tabs, Text, Title } from '@mantine/core';
import { IconArrowLeft, IconBrandSteam, IconChevronDown, IconLayoutKanban, IconVocabulary } from '@tabler/icons-react';

import { FEATURES } from '../../config/features';
import ProjectGlossaryPanel from '../project/ProjectGlossaryPanel';
import ProjectHistory from '../project/ProjectHistory';
import ProjectValidation from '../project/ProjectValidation';
import KanbanBoard from '../tools/KanbanBoard';
import ProjectOverview from '../tools/ProjectOverview';
import SteamWorkshopOverview from '../steamWorkshop/SteamWorkshopOverview';
import surfaceStyles from '../project/ProjectDetailSurfaces.module.css';
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
    <div data-remis-surface="canvas" className={styles.projectCanvas} style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Paper id="project-dashboard-header" data-remis-surface="paper" p="md" shadow="xs" className={surfaceStyles.paperPanel} style={{ zIndex: 10 }}>
        <Group justify="space-between">
          <Group>
            <Button variant="subtle" onClick={() => setSelectedProjectId(null)} leftSection={<IconArrowLeft size={16} />}>
              {t('button_back')}
            </Button>
            <Title order={3} className={surfaceStyles.paperTitle} style={{ fontFamily: 'var(--font-header)' }}>
              {selectedProject.name}
            </Title>
            <Badge color={selectedProject.status === 'active' ? 'blue' : selectedProject.status === 'archived' ? 'orange' : 'red'}>
              {t(`project_management.status.${selectedProject.status}`)}
            </Badge>
          </Group>
          <Badge size="lg">{selectedProject.game_id}</Badge>
        </Group>
      </Paper>

      <Tabs value={activeTab} onChange={setActiveTab} keepMounted={false} variant="outline" radius="md" style={{ flex: 1, display: 'flex', flexDirection: 'column' }} classNames={{
        root: styles.tabsRoot,
        list: styles.tabsList,
        panel: styles.tabsPanel,
      }}>
        <Tabs.List id="project-dashboard-tabs" style={{ paddingLeft: '1rem', paddingTop: '0.5rem', background: 'rgba(0,0,0,0.1)' }}>
          <Tabs.Tab value="overview">{t('project_management.tabs_overview')}</Tabs.Tab>
          <Tabs.Tab value="validation" id="validation-tab-control">{t('project_management.tabs_validation')}</Tabs.Tab>
          {FEATURES.ENABLE_PROJECT_HISTORY && <Tabs.Tab value="history" id="history-tab-control">{t('project_management.tabs_history', 'Project History')}</Tabs.Tab>}
          <Menu position="bottom-start" withinPortal shadow="md">
            <Menu.Target>
              <Button
                variant={['project_glossary', 'taskboard', 'publishing_assets'].includes(activeTab) ? 'light' : 'subtle'}
                size="compact-sm"
                rightSection={<IconChevronDown size={14} />}
                ml="xs"
              >
                {t('project_management.more_views')}
              </Button>
            </Menu.Target>
            <Menu.Dropdown data-remis-surface="elevated" className={surfaceStyles.projectMenuDropdown}>
              <Menu.Item leftSection={<IconVocabulary size={16} />} onClick={() => setActiveTab('project_glossary')}>
                {t('project_management.tabs_project_glossary')}
              </Menu.Item>
              <Menu.Item leftSection={<IconLayoutKanban size={16} />} onClick={() => setActiveTab('taskboard')}>
                {t('project_management.tabs_kanban')}
              </Menu.Item>
              <Menu.Item leftSection={<IconBrandSteam size={16} />} onClick={() => setActiveTab('publishing_assets')}>
                {t('project_management.tabs_publishing_assets', '发布素材管理')}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Tabs.List>

        <Tabs.Panel id="project-dashboard-overview" value="overview" style={{ flex: 1, overflow: 'auto', padding: '1rem', minHeight: 0 }}>
          {projectDetails ? (
            <ProjectOverview
              projectDetails={projectDetails}
              handleProofread={handleProofread}
              handleStatusChange={handleUpdateStatus}
              onFileStatusChange={handleFileStatusChange}
              handleNotesChange={handleUpdateNotes}
              onPathsUpdated={() => fetchProjectFiles(selectedProject.project_id)}
              onDeleteForever={() => setDeleteModalOpen(true)}
              onManageProject={handleOpenManage}
              onRefresh={handleRefreshFiles}
              onRepairMetadata={handleRepairMetadata}
              repairingMetadata={metadataRepairLoading}
            />
          ) : <Text>Loading details...</Text>}
        </Tabs.Panel>

        <Tabs.Panel value="taskboard" style={{ flex: 1, overflow: 'auto', position: 'relative', minHeight: 0 }}>
          <KanbanBoard projectId={selectedProject.project_id} key={selectedProject.project_id + (projectDetails?.refreshKey || '')} />
        </Tabs.Panel>

        <Tabs.Panel value="project_glossary" style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
          <ProjectGlossaryPanel project={selectedProject} t={t} />
        </Tabs.Panel>

        <Tabs.Panel value="publishing_assets" style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
          <SteamWorkshopOverview
            projectId={selectedProject.project_id}
            projectName={selectedProject.name}
          />
        </Tabs.Panel>

        <Tabs.Panel value="validation" style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
          <ProjectValidation projectId={selectedProject.project_id} />
        </Tabs.Panel>

        {FEATURES.ENABLE_PROJECT_HISTORY && (
          <Tabs.Panel value="history" style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
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

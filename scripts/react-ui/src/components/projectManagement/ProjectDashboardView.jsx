import React, { useEffect, useRef } from 'react';
import { Badge, Button, Group, Paper, Tabs, Text, Title, Tooltip } from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';

import { FEATURES } from '../../config/features';
import ProjectHistory from '../project/ProjectHistory';
import ProjectValidation from '../project/ProjectValidation';
import KanbanBoard from '../tools/KanbanBoard';
import ProjectOverview from '../tools/ProjectOverview';
import styles from '../../pages/ProjectManagement.module.css';

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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Paper p="md" shadow="xs" style={{ zIndex: 10 }}>
        <Group justify="space-between">
          <Group>
            <Button variant="subtle" onClick={() => setSelectedProjectId(null)} leftSection={<IconArrowLeft size={16} />}>
              {t('button_back')}
            </Button>
            <Title order={3} style={{ fontFamily: 'var(--font-header)', color: 'var(--text-highlight)' }}>
              {selectedProject.name}
            </Title>
            <Badge color={selectedProject.status === 'active' ? 'blue' : selectedProject.status === 'archived' ? 'orange' : 'red'}>
              {t(`project_management.status.${selectedProject.status}`)}
            </Badge>
          </Group>
          <Group>
            <Tooltip label={t('project_management.tooltip_refresh')}>
              <Button variant="light" size="xs" onClick={handleRefreshFiles}>{t('project_management.refresh_files')}</Button>
            </Tooltip>
            <Badge size="lg">{selectedProject.game_id}</Badge>
          </Group>
        </Group>
      </Paper>

      <Tabs value={activeTab} onChange={setActiveTab} keepMounted={false} variant="outline" radius="md" style={{ flex: 1, display: 'flex', flexDirection: 'column' }} classNames={{
        root: styles.tabsRoot,
        list: styles.tabsList,
        panel: styles.tabsPanel,
      }}>
        <Tabs.List style={{ paddingLeft: '1rem', paddingTop: '0.5rem', background: 'rgba(0,0,0,0.1)' }}>
          <Tabs.Tab value="overview">{t('project_management.tabs_overview')}</Tabs.Tab>
          <Tabs.Tab value="taskboard" id="kanban-tab-control">{t('project_management.tabs_kanban')}</Tabs.Tab>
          <Tabs.Tab value="validation" id="validation-tab-control">{t('project_management.tabs_validation')}</Tabs.Tab>
          {FEATURES.ENABLE_PROJECT_HISTORY && <Tabs.Tab value="history" id="history-tab-control">{t('project_management.tabs_history', 'Project History')}</Tabs.Tab>}
        </Tabs.List>

        <Tabs.Panel value="overview" style={{ flex: 1, overflow: 'auto', padding: '1rem', minHeight: 0 }}>
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

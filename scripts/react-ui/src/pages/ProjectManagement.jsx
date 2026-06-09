import React, { useState, useEffect } from 'react';
import {
  Container, Title, Button, Group, Card, Text, Grid, Modal, TextInput, Select,
  Stack, Badge, ScrollArea, Table, Box, Tabs, Center, Paper, BackgroundImage,
  ActionIcon, SimpleGrid, Overlay, Input, Tooltip, Checkbox, Alert, SegmentedControl,
  Progress
} from '@mantine/core';
import { IconPlus, IconFolder, IconEdit, IconArrowLeft, IconSearch, IconBooks, IconCompass, IconArrowRight, IconArchive, IconTrash, IconRestore, IconAlertTriangle, IconLink, IconCopy } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../context/NotificationContextCore';
import { useTutorial } from '../context/TutorialContextCore';
import { useProjectManagementActions } from '../hooks/useProjectManagementActions';
import { useProjectManagementData } from '../hooks/useProjectManagementData';

// Restore original components
import ProjectOverview from '../components/tools/ProjectOverview';
import KanbanBoard from '../components/tools/KanbanBoard';
import ProjectHistory from '../components/project/ProjectHistory';
import ProjectValidation from '../components/project/ProjectValidation';
import styles from './ProjectManagement.module.css';

// Assets
import heroBg from '../assets/project_hero_bg.png';
import cardNewProject from '../assets/card_new_project.png';
import cardOpenProject from '../assets/card_open_project.png'; // Reusing for Archives

// API_BASE is handled by axios instance 'api'
import { FEATURES } from '../config/features';


export default function ProjectManagement() {
  const { t } = useTranslation();
  const { setPageContext } = useTutorial();
  const { notificationStyle } = useNotification();
  const {
    activeTab,
    availableGames,
    availableLanguages,
    fetchProjectFiles,
    fetchProjects,
    projectDataRefreshToken,
    projectDetails,
    projects,
    selectedProject,
    setActiveTab,
    setProjectDataRefreshToken,
    setProjectDetails,
    setProjects,
    setSelectedProjectId,
    setViewMode,
    viewMode,
  } = useProjectManagementData();
  const [searchQuery, setSearchQuery] = useState('');

  const navigate = useNavigate();
  const {
    createProgressMessage,
    deleteModalOpen,
    deleteSourceFiles,
    editGameId,
    editSourceLang,
    handleBrowseFolder,
    handleCreateProject,
    handleDeleteForever,
    handleFileStatusChange,
    handleOpenManage,
    handleProofread,
    handleRefreshFiles,
    handleRepairMetadata,
    handleUpdateMetadata,
    handleUpdateNotes,
    handleUpdateStatus,
    isCreateModalOpen,
    isCreatingProject,
    manageModalOpen,
    metadataRepairLoading,
    newProjectGame,
    newProjectImportMode,
    newProjectName,
    newProjectPath,
    newProjectSourceLang,
    setDeleteModalOpen,
    setDeleteSourceFiles,
    setEditGameId,
    setEditSourceLang,
    setIsCreateModalOpen,
    setManageModalOpen,
    setNewProjectGame,
    setNewProjectImportMode,
    setNewProjectName,
    setNewProjectPath,
    setNewProjectSourceLang,
  } = useProjectManagementActions({
    fetchProjectFiles,
    fetchProjects,
    navigate,
    notificationStyle,
    projectDetails,
    selectedProject,
    setProjectDataRefreshToken,
    setProjectDetails,
    setProjects,
    setSelectedProjectId,
    viewMode,
  });

  useEffect(() => {
    if (!selectedProject) {
      setPageContext('project-management-list');
      return;
    }

    if (activeTab === 'validation') {
      setPageContext('project-management-validation');
      return;
    }

    if (activeTab === 'history') {
      setPageContext('project-management-history');
      return;
    }

    setPageContext('project-management-dashboard');
  }, [activeTab, selectedProject, setPageContext]);

  // --- Render Views ---

  // View 1: Project List (Hero UI)
  const renderProjectList = () => {
    const filteredProjects = projects.filter(p =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.game_id.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
      <div id="project-list-container" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Hero Section */}
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
                  onChange={(e) => setSearchQuery(e.currentTarget.value)}
                  styles={{ input: { background: 'rgba(255,255,255,0.1)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)' } }}
                />
              </Group>
            </Center>
          </BackgroundImage>
        </Box>

        {/* Content Section */}
        <ScrollArea style={{ flex: 1, padding: '20px' }}>
          {viewMode === 'active' && (
            <>
              <Title order={3} mb="md">Actions</Title>
              <SimpleGrid cols={3} gap="lg" breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>

                {/* Create New Card */}
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

                {/* Archives Card */}
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
            {filteredProjects.map(project => (
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
                  {project.notes || t('project_management.no_notes', "No notes")}
                </Text>
                <Group mt="md">
                  <Text size="xs" color="dimmed">
                    {t('project_management.last_updated', 'Last updated')}: {new Date(project.last_updated || Date.now()).toLocaleDateString()}
                  </Text>
                </Group>
              </Card>
            ))}
          </SimpleGrid>
        </ScrollArea>
      </div>
    );
  };

  const renderProjectDashboard = () => (
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
        panel: styles.tabsPanel
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
                setProjectDataRefreshToken(prev => prev + 1);
                return refreshPromise;
              }}
            />
          </Tabs.Panel>
        )}
      </Tabs>
    </div>
  );

  return (
    <>
      {selectedProject ? renderProjectDashboard() : renderProjectList()}

      <Modal
        opened={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title={t('project_management.actions.create_new')}
        size="lg"
        closeOnClickOutside={!isCreatingProject}
        closeOnEscape={!isCreatingProject}
      >
        <Stack>
          <TextInput
            label={t('form_label_project_name')}
            placeholder={t('form_placeholder_project_name')}
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.currentTarget.value)}
          />
          <Group align="flex-end">
            <TextInput
              label={t('form_label_folder_path')}
              placeholder={t('form_placeholder_folder_path')}
              description={t('form_desc_folder_path')}
              value={newProjectPath}
              onChange={(e) => setNewProjectPath(e.currentTarget.value)}
              style={{ flex: 1 }}
              disabled={isCreatingProject}
            />
            <Button onClick={handleBrowseFolder} leftSection={<IconFolder size={16} />} disabled={isCreatingProject}>
              {t('btn_browse')}
            </Button>
          </Group>
          <SegmentedControl
            fullWidth
            value={newProjectImportMode}
            onChange={setNewProjectImportMode}
            disabled={isCreatingProject}
            data={[
              { value: 'copy', label: t('project_management.import_mode_copy') },
              { value: 'reference', label: t('project_management.import_mode_reference') }
            ]}
          />
          <Alert
            color={newProjectImportMode === 'reference' ? 'yellow' : 'blue'}
            variant="light"
            icon={newProjectImportMode === 'reference' ? <IconLink size={16} /> : <IconCopy size={16} />}
          >
            <Text size="sm">
              {newProjectImportMode === 'reference'
                ? t('project_management.import_mode_reference_desc')
                : t('project_management.import_mode_copy_desc')}
            </Text>
          </Alert>
          <Select
            label={t('form_label_game')}
            data={availableGames.length > 0 ? availableGames : [
              { value: 'stellaris', label: 'Stellaris' },
              { value: 'hoi4', label: 'Hearts of Iron IV' },
              { value: 'vic3', label: 'Victoria 3' },
              { value: 'ck3', label: 'Crusader Kings III' },
              { value: 'eu4', label: 'Europa Universalis IV' }
            ]}
            value={newProjectGame}
            onChange={(val) => setNewProjectGame(val)}
            disabled={isCreatingProject}
          />
          <Select
            label={t('form_label_source_language')}
            description={t('form_desc_source_language')}
            data={availableLanguages.length > 0 ? availableLanguages : [
              { value: 'en', label: 'English' },
              { value: 'zh-CN', label: 'Simplified Chinese' }
            ]}
            value={newProjectSourceLang}
            onChange={(val) => setNewProjectSourceLang(val)}
            disabled={isCreatingProject}
          />
          {isCreatingProject && (
            <Box>
              <Progress value={100} animated striped />
              <Text size="sm" c="dimmed" mt="xs">{createProgressMessage}</Text>
            </Box>
          )}
          {!isCreatingProject && createProgressMessage && (
            <Text size="sm" c="yellow">{createProgressMessage}</Text>
          )}
          <Button
            onClick={handleCreateProject}
            fullWidth
            mt="md"
            loading={isCreatingProject}
            disabled={!newProjectName || !newProjectPath}
          >
            {isCreatingProject ? t('project_management.create_progress_title') : t('project_management.actions.create_new')}
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={deleteModalOpen}
        onClose={() => { setDeleteModalOpen(false); setDeleteSourceFiles(false); }}
        title={
          <Group>
            <IconAlertTriangle color="red" size={24} />
            <Text fw={700} c="red">{t('project_management.delete_forever')}</Text>
          </Group>
        }
        size="md"
        centered
      >
        <Stack>
          <Alert color="red" variant="light" icon={<IconAlertTriangle size={16} />}>
            <Text size="sm" fw={600}>{t('project_management.delete_modal_warning')}</Text>
            <Text size="xs" c="dimmed" mt={4}>{t('project_management.delete_modal_warning_desc')}</Text>
          </Alert>

          <Text size="sm">
            {t('project_management.delete_modal_question')}
          </Text>
          <Paper withBorder p="xs" bg="rgba(255, 0, 0, 0.05)">
            <Text size="sm" fw={600}>{selectedProject?.name}</Text>
            <Text size="xs" c="dimmed">{selectedProject?.source_path}</Text>
          </Paper>

          <Checkbox
            checked={deleteSourceFiles}
            onChange={(e) => setDeleteSourceFiles(e.currentTarget.checked)}
            label={
              <div>
                <Text size="sm" fw={600} c="red">{t('project_management.delete_modal_source_files_label')}</Text>
                <Text size="xs" c="dimmed">{t('project_management.delete_modal_source_files_desc')}</Text>
              </div>
            }
            color="red"
            size="md"
            mt="md"
          />

          <Group justify="flex-end" mt="xl">
            <Button variant="default" onClick={() => { setDeleteModalOpen(false); setDeleteSourceFiles(false); }}>
              {t('button_cancel')}
            </Button>
            <Button color="red" leftSection={<IconTrash size={16} />} onClick={handleDeleteForever}>
              {deleteSourceFiles ? t('project_management.delete_modal_btn_with_files') : t('project_management.delete_modal_btn_config_only')}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={manageModalOpen}
        onClose={() => setManageModalOpen(false)}
        title={t('project_management.manage_project')}
        size="lg"
      >
        <Stack>
          <Select
            label={t('form_label_game')}
            data={availableGames.length > 0 ? availableGames : [
              { value: 'stellaris', label: 'Stellaris' },
              { value: 'hoi4', label: 'Hearts of Iron IV' },
              { value: 'vic3', label: 'Victoria 3' },
              { value: 'ck3', label: 'Crusader Kings III' },
              { value: 'eu4', label: 'Europa Universalis IV' }
            ]}
            value={editGameId ? editGameId.toLowerCase() : ''}
            onChange={setEditGameId}
          />
          <Select
            label={t('form_label_source_language')}
            data={availableLanguages.length > 0 ? availableLanguages : [
              { value: 'en', label: 'English' },
              { value: 'zh-CN', label: 'Simplified Chinese' }
            ]}
            value={editSourceLang}
            onChange={setEditSourceLang}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setManageModalOpen(false)}>{t('button_cancel')}</Button>
            <Button onClick={handleUpdateMetadata}>{t('settings_save')}</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

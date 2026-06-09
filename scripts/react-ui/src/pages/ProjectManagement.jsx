import React, { useState, useEffect } from 'react';
import {
  Button, Group, Text, Modal, TextInput, Select,
  Stack, Paper, Box, Checkbox, Alert, SegmentedControl,
  Progress
} from '@mantine/core';
import { IconFolder, IconTrash, IconAlertTriangle, IconLink, IconCopy } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../context/NotificationContextCore';
import { useTutorial } from '../context/TutorialContextCore';
import { ProjectDashboardView } from '../components/projectManagement/ProjectDashboardView';
import { ProjectListView } from '../components/projectManagement/ProjectListView';
import { useProjectManagementActions } from '../hooks/useProjectManagementActions';
import { useProjectManagementData } from '../hooks/useProjectManagementData';

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

  return (
    <>
      {selectedProject ? (
        <ProjectDashboardView
          activeTab={activeTab}
          fetchProjectFiles={fetchProjectFiles}
          fetchProjects={fetchProjects}
          handleFileStatusChange={handleFileStatusChange}
          handleOpenManage={handleOpenManage}
          handleProofread={handleProofread}
          handleRefreshFiles={handleRefreshFiles}
          handleRepairMetadata={handleRepairMetadata}
          handleUpdateNotes={handleUpdateNotes}
          handleUpdateStatus={handleUpdateStatus}
          metadataRepairLoading={metadataRepairLoading}
          projectDataRefreshToken={projectDataRefreshToken}
          projectDetails={projectDetails}
          selectedProject={selectedProject}
          setActiveTab={setActiveTab}
          setDeleteModalOpen={setDeleteModalOpen}
          setProjectDataRefreshToken={setProjectDataRefreshToken}
          setSelectedProjectId={setSelectedProjectId}
          t={t}
        />
      ) : (
        <ProjectListView
          projects={projects}
          searchQuery={searchQuery}
          setIsCreateModalOpen={setIsCreateModalOpen}
          setSearchQuery={setSearchQuery}
          setSelectedProjectId={setSelectedProjectId}
          setViewMode={setViewMode}
          t={t}
          viewMode={viewMode}
        />
      )}

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

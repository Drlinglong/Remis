import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../context/NotificationContextCore';
import { useTutorial } from '../context/TutorialContextCore';
import { CreateProjectModal } from '../components/projectManagement/CreateProjectModal';
import { DeleteProjectModal } from '../components/projectManagement/DeleteProjectModal';
import { ManageProjectModal } from '../components/projectManagement/ManageProjectModal';
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

      <CreateProjectModal
        availableGames={availableGames}
        availableLanguages={availableLanguages}
        createProgressMessage={createProgressMessage}
        handleBrowseFolder={handleBrowseFolder}
        handleCreateProject={handleCreateProject}
        isCreatingProject={isCreatingProject}
        newProjectGame={newProjectGame}
        newProjectImportMode={newProjectImportMode}
        newProjectName={newProjectName}
        newProjectPath={newProjectPath}
        newProjectSourceLang={newProjectSourceLang}
        opened={isCreateModalOpen}
        setNewProjectGame={setNewProjectGame}
        setNewProjectImportMode={setNewProjectImportMode}
        setNewProjectName={setNewProjectName}
        setNewProjectPath={setNewProjectPath}
        setNewProjectSourceLang={setNewProjectSourceLang}
        t={t}
        onClose={() => setIsCreateModalOpen(false)}
      />

      <DeleteProjectModal
        deleteSourceFiles={deleteSourceFiles}
        handleDeleteForever={handleDeleteForever}
        opened={deleteModalOpen}
        selectedProject={selectedProject}
        setDeleteSourceFiles={setDeleteSourceFiles}
        t={t}
        onClose={() => setDeleteModalOpen(false)}
      />

      <ManageProjectModal
        availableGames={availableGames}
        availableLanguages={availableLanguages}
        editGameId={editGameId}
        editSourceLang={editSourceLang}
        handleUpdateMetadata={handleUpdateMetadata}
        opened={manageModalOpen}
        setEditGameId={setEditGameId}
        setEditSourceLang={setEditSourceLang}
        t={t}
        onClose={() => setManageModalOpen(false)}
      />
    </>
  );
}

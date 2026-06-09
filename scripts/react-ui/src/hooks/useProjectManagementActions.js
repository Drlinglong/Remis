import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { open } from '@tauri-apps/plugin-dialog';

import notificationService from '../services/notificationService';
import projectService from '../services/projectService';

const normalizeGameId = (gameId) => {
  const gameMap = { vic3: 'victoria3', 'victoria 3': 'victoria3' };
  const normalized = (gameId || 'stellaris').toLowerCase();
  return gameMap[normalized] || normalized;
};

export function useProjectManagementActions({
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
}) {
  const { t, i18n } = useTranslation();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteSourceFiles, setDeleteSourceFiles] = useState(false);
  const [metadataRepairLoading, setMetadataRepairLoading] = useState(false);

  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectPath, setNewProjectPath] = useState('');
  const [newProjectGame, setNewProjectGame] = useState('stellaris');
  const [newProjectSourceLang, setNewProjectSourceLang] = useState('en');
  const [newProjectImportMode, setNewProjectImportMode] = useState('copy');
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [createProgressMessage, setCreateProgressMessage] = useState('');

  const [manageModalOpen, setManageModalOpen] = useState(false);
  const [editGameId, setEditGameId] = useState('');
  const [editSourceLang, setEditSourceLang] = useState('');

  const refreshProjectData = useCallback(async () => {
    if (!selectedProject) return;

    await Promise.all([
      fetchProjects(),
      fetchProjectFiles(selectedProject.project_id),
    ]);
    setProjectDataRefreshToken((prev) => prev + 1);
    setProjectDetails((prev) => ({ ...prev, refreshKey: Date.now() }));
  }, [fetchProjectFiles, fetchProjects, selectedProject, setProjectDataRefreshToken, setProjectDetails]);

  const handleCreateProject = useCallback(async () => {
    if (!newProjectName || !newProjectPath) {
      setCreateProgressMessage(t('project_management.create_missing_fields'));
      return;
    }

    setIsCreatingProject(true);
    setCreateProgressMessage(
      newProjectImportMode === 'copy'
        ? t('project_management.create_progress_copying')
        : t('project_management.create_progress_referencing')
    );

    try {
      const response = await projectService.createProject({
        name: newProjectName,
        folder_path: newProjectPath,
        game_id: newProjectGame,
        source_language: newProjectSourceLang,
        import_mode: newProjectImportMode,
      });
      setCreateProgressMessage(t('project_management.create_progress_refreshing'));
      setIsCreateModalOpen(false);
      await fetchProjects();
      setNewProjectName('');
      setNewProjectPath('');
      setCreateProgressMessage('');

      const createdProjectId = response.data?.project?.project_id || response.data?.project_id;
      if (createdProjectId) {
        setSelectedProjectId(createdProjectId);
      }
    } catch (error) {
      setCreateProgressMessage('');
      alert(`Failed to create project: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsCreatingProject(false);
    }
  }, [
    fetchProjects,
    newProjectGame,
    newProjectImportMode,
    newProjectName,
    newProjectPath,
    newProjectSourceLang,
    setSelectedProjectId,
    t,
  ]);

  const handleBrowseFolder = useCallback(async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: 'Select Project Folder',
      });
      if (selected && typeof selected === 'string') {
        setNewProjectPath(selected);
      }
    } catch (error) {
      console.error('Failed to open dialog:', error);
    }
  }, []);

  const handleProofread = useCallback((file) => {
    if (!selectedProject) {
      console.error('No selected project!');
      return;
    }

    const fileId = file.key || file.file_id;
    if (!fileId) {
      console.error('No fileId found in file object:', file);
      alert('Error: Cannot identify file. Please refresh the project.');
      return;
    }

    navigate(`/proofreading?projectId=${selectedProject.project_id}&fileId=${fileId}`);
  }, [navigate, selectedProject]);

  const handleUpdateNotes = useCallback(async (notes) => {
    if (!selectedProject) return;
    try {
      await projectService.updateProjectNotes(selectedProject.project_id, { notes });
      setProjects((prev) => prev.map((project) => (
        project.project_id === selectedProject.project_id ? { ...project, notes } : project
      )));
      setProjectDetails((prev) => ({ ...prev, notes }));
    } catch (error) {
      console.error('Failed to update notes', error);
      alert('Failed to save notes');
    }
  }, [selectedProject, setProjectDetails, setProjects]);

  const handleUpdateStatus = useCallback(async (status) => {
    if (!selectedProject) return;
    try {
      await projectService.updateProjectStatus(selectedProject.project_id, { status });
      setProjects((prev) => prev.map((project) => (
        project.project_id === selectedProject.project_id ? { ...project, status } : project
      )));
      setProjectDetails((prev) => ({ ...prev, status }));
      fetchProjects();

      if ((viewMode === 'active' && status !== 'active') || (viewMode === 'archives' && status === 'active')) {
        setSelectedProjectId(null);
      }
    } catch (error) {
      console.error('Failed to update status', error);
      alert('Failed to update status');
    }
  }, [fetchProjects, selectedProject, setProjectDetails, setProjects, setSelectedProjectId, viewMode]);

  const handleFileStatusChange = useCallback(async (fileId, status) => {
    if (!selectedProject) return;
    try {
      await projectService.updateFileStatus(selectedProject.project_id, fileId, { status });
      fetchProjectFiles(selectedProject.project_id);
    } catch (error) {
      console.error('Failed to update file status', error);
      alert('Failed to update file status');
    }
  }, [fetchProjectFiles, selectedProject]);

  const handleOpenManage = useCallback(() => {
    if (!selectedProject) return;

    setEditGameId(normalizeGameId(selectedProject.game_id));
    setEditSourceLang(selectedProject.source_language || 'en');
    setManageModalOpen(true);
  }, [selectedProject]);

  const handleUpdateMetadata = useCallback(async () => {
    if (!selectedProject) return;
    try {
      await projectService.updateProjectMetadata(selectedProject.project_id, {
        game_id: editGameId,
        source_language: editSourceLang,
      });

      setProjects((prev) => prev.map((project) => (
        project.project_id === selectedProject.project_id
          ? { ...project, game_id: editGameId, source_language: editSourceLang }
          : project
      )));

      if (projectDetails) {
        setProjectDetails((prev) => ({
          ...prev,
          game_id: editGameId,
          source_language: editSourceLang,
        }));
      }

      notificationService.success(t('api_key_success_title'), notificationStyle);
      setManageModalOpen(false);
    } catch (error) {
      alert(`Failed to update project: ${error.response?.data?.detail || error.message} `);
    }
  }, [
    editGameId,
    editSourceLang,
    notificationStyle,
    projectDetails,
    selectedProject,
    setProjectDetails,
    setProjects,
    t,
  ]);

  const handleDeleteForever = useCallback(async () => {
    if (!selectedProject) return;
    try {
      await projectService.deleteProject(selectedProject.project_id, deleteSourceFiles);
      setDeleteModalOpen(false);
      setSelectedProjectId(null);
      setDeleteSourceFiles(false);
      fetchProjects();
    } catch (error) {
      alert(`Failed to delete project: ${error.response?.data?.detail || error.message}`);
    }
  }, [deleteSourceFiles, fetchProjects, selectedProject, setSelectedProjectId]);

  const handleRefreshFiles = useCallback(async () => {
    if (!selectedProject) return;
    try {
      await projectService.refreshProjectFiles(selectedProject.project_id);
      await refreshProjectData();
    } catch (error) {
      console.error('Failed to refresh files', error);
    }
  }, [refreshProjectData, selectedProject]);

  const formatRepairMetadataNotification = useCallback((metadata) => {
    const isChinese = (i18n.language || '').toLowerCase().startsWith('zh');
    const actions = Array.isArray(metadata?.actions) ? metadata.actions : [];
    const warnings = Array.isArray(metadata?.warnings) ? metadata.warnings : [];
    const updatedFiles = new Set();

    if (actions.some((action) => [
      'created_project_sidecar',
      'deduplicated_translation_dir',
      'repaired_kanban_metadata',
    ].includes(action))) {
      updatedFiles.add('.remis_project.json');
    }
    if (actions.some((action) => [
      'cleared_stale_project_error_cache',
      'rebuilt_invalid_error_cache',
    ].includes(action))) {
      updatedFiles.add('.remis_errors.json');
    }

    const fileIndexText = isChinese
      ? `项目文件索引已刷新（${metadata?.file_count ?? 0} 个文件）`
      : `Project file index refreshed (${metadata?.file_count ?? 0} files)`;
    const updatedText = updatedFiles.size
      ? (isChinese ? `更新文件：${Array.from(updatedFiles).join('、')}` : `Updated files: ${Array.from(updatedFiles).join(', ')}`)
      : (isChinese ? '元数据文件已校验，无需改写' : 'Metadata files checked; no metadata file rewrite needed');
    const translationDirText = isChinese
      ? `翻译目录：${metadata?.translation_dirs?.length ?? 0} 个`
      : `Translation dirs: ${metadata?.translation_dirs?.length ?? 0}`;
    const warningText = warnings.length
      ? (isChinese ? `警告：${warnings.length} 个（${warnings[0]}）` : `Warnings: ${warnings.length} (${warnings[0]})`)
      : (isChinese ? '无警告' : 'No warnings');

    return [
      t('project_management.repair_metadata_success', isChinese ? '项目元数据检验/重建成功。' : 'Project metadata checked/rebuilt successfully.'),
      updatedText,
      fileIndexText,
      translationDirText,
      warningText,
    ].join('\n');
  }, [i18n.language, t]);

  const handleRepairMetadata = useCallback(async () => {
    if (!selectedProject || metadataRepairLoading) return;
    setMetadataRepairLoading(true);
    try {
      const response = await projectService.repairProjectMetadata(selectedProject.project_id);
      await refreshProjectData();
      notificationService.success(
        formatRepairMetadataNotification(response.data || {}),
        notificationStyle
      );
    } catch (error) {
      console.error('Failed to repair metadata', error);
      const isChinese = (i18n.language || '').toLowerCase().startsWith('zh');
      const failureDetail = error.response?.data?.detail || t('project_management.repair_metadata_error', 'Failed to repair project metadata.');
      notificationService.error(
        isChinese ? `项目元数据检验/重建失败：${failureDetail}` : `Project metadata repair failed: ${failureDetail}`,
        notificationStyle
      );
    } finally {
      setMetadataRepairLoading(false);
    }
  }, [
    formatRepairMetadataNotification,
    i18n.language,
    metadataRepairLoading,
    notificationStyle,
    refreshProjectData,
    selectedProject,
    t,
  ]);

  return {
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
  };
}

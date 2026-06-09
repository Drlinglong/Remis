import { useCallback, useEffect, useState } from 'react';

import configService from '../services/configService';
import projectService from '../services/projectService';
import { usePersistentState } from './usePersistentState';

const buildProjectDetails = ({ archiveInfo, config, files, project, projectId }) => {
  const totalLines = files.reduce((acc, file) => acc + (file.line_count || 0), 0);
  const doneCount = files.filter((file) => file.status === 'done').length;
  const proofreadCount = files.filter((file) => file.status === 'proofreading' || file.status === 'todo').length;

  return {
    project_id: projectId,
    game_id: project.game_id,
    name: project.name,
    status: project.status,
    notes: project.notes,
    source_language: config.source_language || project.source_language,
    archived_languages: archiveInfo?.archived_languages || [],
    archive_summary: archiveInfo ? {
      version_id: archiveInfo.version_id,
      created_at: archiveInfo.created_at,
      last_upload_at: archiveInfo.last_upload_at,
      source_entry_count: archiveInfo.source_entry_count || 0,
      source_file_count: archiveInfo.source_file_count || 0,
      total_translation_entries: archiveInfo.total_translation_entries || 0,
      target_language_count: archiveInfo.target_language_count || 0,
      baseline_versions: archiveInfo.baseline_versions || [],
    } : null,
    overview: {
      totalFiles: files.length,
      totalLines,
      translated: Math.round((doneCount / files.length) * 100) || 0,
      toBeProofread: Math.round((proofreadCount / files.length) * 100) || 0,
      glossary: 'Default',
    },
    source_path: config.source_path,
    translation_dirs: config.translation_dirs,
    files: files.map((file) => ({
      key: file.file_id,
      name: file.file_path,
      status: file.status,
      lines: file.line_count,
      file_type: file.file_type,
      progress: file.status === 'done' ? '100%' : '0%',
      actions: ['Proofread'],
    })),
  };
};

export function useProjectManagementData() {
  const [projects, setProjects] = useState([]);
  const [availableGames, setAvailableGames] = useState([]);
  const [availableLanguages, setAvailableLanguages] = useState([]);
  const [projectDetails, setProjectDetails] = useState(null);
  const [projectDataRefreshToken, setProjectDataRefreshToken] = useState(0);

  const [viewMode, setViewMode] = usePersistentState('pm_view_mode', 'active');
  const [selectedProjectId, setSelectedProjectId] = usePersistentState('pm_selected_project_id', null);
  const [activeTab, setActiveTab] = usePersistentState('pm_active_tab', 'overview');

  const selectedProject = projects.find((project) => project.project_id === selectedProjectId) || null;

  const fetchGameConfig = useCallback(async () => {
    try {
      const response = await configService.getConfig();
      if (response.data?.game_profiles) {
        setAvailableGames(Object.values(response.data.game_profiles).map((profile) => ({
          value: profile.id,
          label: profile.name,
        })));
      }
      if (response.data?.languages) {
        setAvailableLanguages(Object.values(response.data.languages).map((language) => ({
          value: language.code,
          label: language.name,
        })));
      }
    } catch (error) {
      console.error('Failed to fetch game config', error);
    }
  }, []);

  const fetchProjects = useCallback(async () => {
    try {
      if (viewMode === 'active') {
        const response = await projectService.getProjectsByStatus('active');
        setProjects(response.data);
        return;
      }

      const [archivedResponse, deletedResponse] = await Promise.all([
        projectService.getProjectsByStatus('archived'),
        projectService.getProjectsByStatus('deleted'),
      ]);
      setProjects([...archivedResponse.data, ...deletedResponse.data]);
    } catch (error) {
      console.error('Failed to load projects', error);
    }
  }, [viewMode]);

  const fetchProjectFiles = useCallback(async (projectId) => {
    if (!selectedProject) return;

    try {
      const [filesResponse, configResponse, archiveResponse] = await Promise.all([
        projectService.getProjectFiles(projectId),
        projectService.getProjectConfig(projectId),
        projectService.checkArchive(projectId).catch(() => ({ data: null })),
      ]);

      const archiveInfo = archiveResponse?.data?.exists ? archiveResponse.data : null;
      setProjectDetails(buildProjectDetails({
        archiveInfo,
        config: configResponse.data,
        files: filesResponse.data,
        project: selectedProject,
        projectId,
      }));
    } catch (error) {
      console.error('Failed to load files or config', error);
    }
  }, [selectedProject]);

  useEffect(() => {
    fetchProjects();
    fetchGameConfig();
  }, [fetchGameConfig, fetchProjects]);

  useEffect(() => {
    if (selectedProject) {
      setProjectDetails(null);
      fetchProjectFiles(selectedProject.project_id);
    }
  }, [fetchProjectFiles, selectedProject]);

  return {
    activeTab,
    availableGames,
    availableLanguages,
    fetchProjectFiles,
    fetchProjects,
    projectDataRefreshToken,
    projectDetails,
    projects,
    selectedProject,
    selectedProjectId,
    setActiveTab,
    setProjectDataRefreshToken,
    setProjectDetails,
    setProjects,
    setSelectedProjectId,
    setViewMode,
    viewMode,
  };
}

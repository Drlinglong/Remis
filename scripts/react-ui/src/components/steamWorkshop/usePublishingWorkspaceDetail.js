import { useCallback, useEffect, useMemo, useState } from 'react';
import i18n from '../../i18n/i18n';

import projectService from '../../services/projectService';
import { normalizeArrayPayload } from '../../utils/payload';
import {
  getPublishingWorkspace,
  updatePublishingWorkspace,
} from './description/descriptionService';

export function usePublishingWorkspaceDetail(workspaceId) {
  const [workspace, setWorkspace] = useState(null);
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (!workspaceId) return;
    setError('');
    setIsLoading(true);
    try {
      const [loadedWorkspace, projectResponse] = await Promise.all([
        getPublishingWorkspace(workspaceId),
        projectService.getActiveProjects(),
      ]);
      setWorkspace(loadedWorkspace);
      setProjects(normalizeArrayPayload(
        projectResponse.data,
        ['projects', 'items', 'data', 'results'],
      ));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_load_failed'));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const updateWorkspace = useCallback(async (values) => {
    if (!workspace) return null;
    setError('');
    setIsSaving(true);
    try {
      const updated = await updatePublishingWorkspace(workspace.workspace_id, {
        name: values.name,
        game_id: values.gameId || null,
        project_id: values.projectId || null,
        workshop_item_id: values.workshopItemId || null,
      });
      setWorkspace(updated);
      return updated;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_update_failed'));
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [workspace]);

  const projectName = useMemo(
    () => projects.find((project) => project.project_id === workspace?.project_id)?.name || '',
    [projects, workspace?.project_id],
  );

  return {
    error,
    isLoading,
    isSaving,
    projectName,
    projects,
    refresh,
    updateWorkspace,
    workspace,
  };
}

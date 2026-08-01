import { useCallback, useEffect, useMemo, useState } from 'react';
import i18n from '../../i18n/i18n';

import configService from '../../services/configService';
import projectService from '../../services/projectService';
import { normalizeArrayPayload } from '../../utils/payload';
import {
  createPublishingWorkspace,
  listPublishingWorkspaces,
  updatePublishingWorkspace,
} from './description/descriptionService';

const summarizeWorkspace = (workspace) => ({
  ...workspace,
  current_cover_version: workspace.current_cover_sequence
    ? { sequence: workspace.current_cover_sequence }
    : null,
  current_description_version: workspace.current_description_sequence
    ? { sequence: workspace.current_description_sequence }
    : null,
});

export function usePublishingWorkspaceCatalog({ projectId = null } = {}) {
  const [workspaces, setWorkspaces] = useState([]);
  const [projects, setProjects] = useState([]);
  const [games, setGames] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const [workspaceItems, projectResponse, configResponse] = await Promise.all([
        listPublishingWorkspaces({ projectId }),
        projectService.getActiveProjects(),
        configService.getConfig(),
      ]);
      setProjects(normalizeArrayPayload(
        projectResponse.data,
        ['projects', 'items', 'data', 'results'],
      ));
      const profiles = Object.values(configResponse.data?.game_profiles || {});
      setGames(Array.from(
        new Map(profiles.map((profile) => [profile.id, {
          value: profile.id,
          label: profile.name,
        }])).values(),
      ));
      setWorkspaces(workspaceItems.map(summarizeWorkspace));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_load_failed'));
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const saveWorkspace = useCallback(async (values, workspaceId = null) => {
    setError('');
    setIsSaving(true);
    const payload = {
      name: values.name,
      game_id: values.gameId || null,
      project_id: projectId || values.projectId || null,
      workshop_item_id: values.workshopItemId || null,
    };
    try {
      const workspace = workspaceId
        ? await updatePublishingWorkspace(workspaceId, payload)
        : await createPublishingWorkspace(payload);
      await refresh();
      return workspace;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_save_failed'));
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [projectId, refresh]);

  const projectNames = useMemo(
    () => new Map(projects.map((project) => [project.project_id, project.name])),
    [projects],
  );

  return {
    error,
    isLoading,
    isSaving,
    games,
    projectNames,
    projects,
    refresh,
    saveWorkspace,
    workspaces,
  };
}

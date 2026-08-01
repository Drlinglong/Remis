import { useCallback, useEffect, useState } from 'react';
import i18n from '../../i18n/i18n';

import {
  createPublishingWorkspace,
  getPublishingWorkspace,
  listPublishingWorkspaces,
  updatePublishingWorkspace,
} from './description/descriptionService';

export function usePublishingWorkspaceSelection({ projectId }) {
  const [workspaces, setWorkspaces] = useState([]);
  const [workspace, setWorkspace] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const selectWorkspace = useCallback(async (workspaceId) => {
    setError('');
    if (!workspaceId) {
      setWorkspace(null);
      return;
    }
    try {
      setIsLoading(true);
      setWorkspace(await getPublishingWorkspace(workspaceId));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_load_failed'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setError('');
    try {
      setIsLoading(true);
      const items = await listPublishingWorkspaces({ projectId });
      setWorkspaces(items);
      if (!items.length) {
        setWorkspace(null);
        return;
      }
      const currentId = workspace?.workspace_id;
      const target = items.find((item) => item.workspace_id === currentId) || items[0];
      setWorkspace(await getPublishingWorkspace(target.workspace_id));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.assets_load_failed'));
    } finally {
      setIsLoading(false);
    }
  }, [projectId, workspace?.workspace_id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createWorkspace = useCallback(async ({ name, gameId, workshopItemId }) => {
    setError('');
    try {
      setIsSaving(true);
      const created = await createPublishingWorkspace({
        name,
        game_id: gameId || null,
        project_id: projectId || null,
        workshop_item_id: workshopItemId || null,
      });
      setWorkspaces((current) => [...current, created]);
      setWorkspace(created);
      return created;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_create_failed'));
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [projectId]);

  const updateWorkspace = useCallback(async ({ name, gameId, workshopItemId }) => {
    if (!workspace) return null;
    setError('');
    try {
      setIsSaving(true);
      const updated = await updatePublishingWorkspace(workspace.workspace_id, {
        name,
        game_id: gameId || null,
        workshop_item_id: workshopItemId || null,
      });
      setWorkspaces((current) => current.map((item) => (
        item.workspace_id === updated.workspace_id ? updated : item
      )));
      setWorkspace(updated);
      return updated;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.workspace_update_failed'));
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [workspace]);

  return {
    createWorkspace,
    error,
    isLoading,
    isSaving,
    refresh,
    selectWorkspace,
    updateWorkspace,
    workspace,
    workspaces,
  };
}

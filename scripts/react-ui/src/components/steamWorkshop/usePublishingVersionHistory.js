import { useCallback, useEffect, useMemo, useState } from 'react';
import i18n from '../../i18n/i18n';

import steamWorkshopCoverService from '../../services/steamWorkshopCoverService';
import {
  getPublishingWorkspace,
  deletePublishingVersion,
  listPublishingVersions,
  selectDescriptionVersion,
} from './description/descriptionService';

export function usePublishingVersionHistory(workspaceId) {
  const [workspace, setWorkspace] = useState(null);
  const [versions, setVersions] = useState([]);
  const [filter, setFilter] = useState('all');
  const [openedVersion, setOpenedVersion] = useState(null);
  const [busyVersionId, setBusyVersionId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (!workspaceId) return;
    setError('');
    setIsLoading(true);
    try {
      const [loadedWorkspace, loadedVersions] = await Promise.all([
        getPublishingWorkspace(workspaceId),
        listPublishingVersions(workspaceId),
      ]);
      setWorkspace(loadedWorkspace);
      setVersions(loadedVersions.map((version) => ({
        ...version,
        content_url: steamWorkshopCoverService.resolveMediaUrl(version.content_url),
      })));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.history_load_failed'));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const adoptVersion = useCallback(async (version) => {
    setBusyVersionId(version.version_id);
    setError('');
    try {
      if (version.asset_type === 'cover') {
        await steamWorkshopCoverService.selectVersion(workspaceId, version.version_id);
      } else {
        await selectDescriptionVersion(workspaceId, version.version_id);
      }
      await refresh();
      return true;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.version_adopt_failed'));
      return false;
    } finally {
      setBusyVersionId(null);
    }
  }, [refresh, workspaceId]);

  const deleteVersion = useCallback(async (version) => {
    setBusyVersionId(version.version_id);
    setError('');
    try {
      await deletePublishingVersion(workspaceId, version.version_id);
      setOpenedVersion((current) => (
        current?.version_id === version.version_id ? null : current
      ));
      await refresh();
      return true;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || i18n.t('steam_workshop.version_delete_failed'));
      return false;
    } finally {
      setBusyVersionId(null);
    }
  }, [refresh, workspaceId]);

  const filteredVersions = useMemo(
    () => filter === 'all'
      ? versions
      : versions.filter((version) => version.asset_type === filter),
    [filter, versions],
  );

  const isSelected = useCallback((version) => (
    version.asset_type === 'cover'
      ? workspace?.current_cover_version_id === version.version_id
      : workspace?.current_description_version_id === version.version_id
  ), [workspace]);

  return {
    adoptVersion,
    busyVersionId,
    error,
    deleteVersion,
    filter,
    filteredVersions,
    isLoading,
    isSelected,
    openedVersion,
    refresh,
    setFilter,
    setOpenedVersion,
    versions,
    workspace,
  };
}

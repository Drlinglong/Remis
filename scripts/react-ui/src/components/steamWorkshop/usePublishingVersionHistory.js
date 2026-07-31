import { useCallback, useEffect, useMemo, useState } from 'react';

import steamWorkshopCoverService from '../../services/steamWorkshopCoverService';
import {
  getPublishingWorkspace,
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
      setVersions(loadedVersions);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || '无法读取版本历史。');
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
      setError(requestError.response?.data?.detail || '无法采用这个版本。');
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

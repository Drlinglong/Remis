import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createDescriptionVersion,
  createPublishingWorkspace,
  getPublishingWorkspace,
  generateDescriptionCandidate,
  listDescriptionVersions,
  listPublishingWorkspaces,
  selectDescriptionVersion,
} from './descriptionService';

const EMPTY_EDITOR = { bbcode: '', language: 'zh', parentVersionId: null };

export const useDescriptionWorkspace = ({ projectId, requestedWorkspaceId }) => {
  const [workspaces, setWorkspaces] = useState([]);
  const [workspace, setWorkspace] = useState(null);
  const [versions, setVersions] = useState([]);
  const [editor, setEditor] = useState(EMPTY_EDITOR);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  const loadVersions = useCallback(async (selectedWorkspace) => {
    if (!selectedWorkspace) {
      setVersions([]);
      return;
    }
    setVersions(await listDescriptionVersions(selectedWorkspace.workspace_id));
  }, []);

  const selectWorkspace = useCallback(async (workspaceId) => {
    setError('');
    if (!workspaceId) {
      setWorkspace(null);
      setVersions([]);
      setEditor(EMPTY_EDITOR);
      return;
    }
    try {
      setIsLoading(true);
      const selectedWorkspace = await getPublishingWorkspace(workspaceId);
      setWorkspace(selectedWorkspace);
      await loadVersions(selectedWorkspace);
    } catch (loadError) {
      setError(loadError.response?.data?.detail || '无法读取发布工作区。');
    } finally {
      setIsLoading(false);
    }
  }, [loadVersions]);

  const refresh = useCallback(async () => {
    setError('');
    try {
      setIsLoading(true);
      const items = await listPublishingWorkspaces({ projectId });
      setWorkspaces(items);
      const targetId = requestedWorkspaceId || items[0]?.workspace_id;
      if (targetId) {
        const selectedWorkspace = await getPublishingWorkspace(targetId);
        setWorkspace(selectedWorkspace);
        await loadVersions(selectedWorkspace);
      } else {
        setWorkspace(null);
        setVersions([]);
      }
    } catch (loadError) {
      setError(loadError.response?.data?.detail || '无法读取发布素材。');
    } finally {
      setIsLoading(false);
    }
  }, [loadVersions, projectId, requestedWorkspaceId]);

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
      setVersions([]);
      setEditor(EMPTY_EDITOR);
      return created;
    } catch (createError) {
      setError(createError.response?.data?.detail || '无法创建发布工作区。');
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [projectId]);

  const saveCandidate = useCallback(async ({ source = 'manual', metadata = {} } = {}) => {
    if (!workspace || !editor.bbcode.trim()) return null;
    setError('');
    try {
      setIsSaving(true);
      const version = await createDescriptionVersion(workspace.workspace_id, {
        bbcode: editor.bbcode,
        language: editor.language,
        source,
        parent_version_id: editor.parentVersionId,
        metadata,
      });
      setVersions((current) => [version, ...current]);
      setEditor((current) => ({ ...current, parentVersionId: version.version_id }));
      return version;
    } catch (saveError) {
      setError(saveError.response?.data?.detail || '候选版本保存失败。');
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [editor, workspace]);

  const chooseVersion = useCallback((version) => {
    setEditor({
      bbcode: version.bbcode,
      language: version.language,
      parentVersionId: version.version_id,
    });
  }, []);

  const adoptVersion = useCallback(async (versionId) => {
    if (!workspace) return false;
    setError('');
    try {
      setIsSaving(true);
      await selectDescriptionVersion(workspace.workspace_id, versionId);
      const updatedWorkspace = await getPublishingWorkspace(workspace.workspace_id);
      setWorkspace(updatedWorkspace);
      await loadVersions(updatedWorkspace);
      return true;
    } catch (selectError) {
      setError(selectError.response?.data?.detail || '无法选择当前采用版本。');
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [loadVersions, workspace]);

  const generateCandidate = useCallback(async (payload) => {
    if (!workspace) return null;
    setError('');
    try {
      setIsGenerating(true);
      const version = await generateDescriptionCandidate(
        workspace.workspace_id,
        payload,
      );
      setVersions((current) => [version, ...current]);
      setEditor({
        bbcode: version.bbcode,
        language: version.language,
        parentVersionId: version.version_id,
      });
      return version;
    } catch (generateError) {
      setError(generateError.response?.data?.detail || '模型生成失败，未创建候选版本。');
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, [workspace]);

  const currentVersionId = workspace?.current_description_version_id || null;
  const currentVersion = useMemo(
    () => versions.find((version) => version.version_id === currentVersionId) || null,
    [currentVersionId, versions],
  );

  return {
    adoptVersion,
    chooseVersion,
    createWorkspace,
    currentVersion,
    editor,
    error,
    generateCandidate,
    isGenerating,
    isLoading,
    isSaving,
    refresh,
    saveCandidate,
    selectWorkspace,
    setEditor,
    versions,
    workspace,
    workspaces,
  };
};

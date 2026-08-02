import { useCallback, useEffect, useState } from 'react';
import steamWorkshopCoverService from '../../../services/steamWorkshopCoverService';

const normalizeVersions = (payload) => Array.isArray(payload) ? payload : payload?.versions || [];

export const useCoverVersions = ({ workspaceId, currentVersionId = null, onLoadCanvas }) => {
    const [versions, setVersions] = useState([]);
    const [selectedVersionId, setSelectedVersionId] = useState(currentVersionId);
    const [editingParentVersionId, setEditingParentVersionId] = useState(currentVersionId);
    const [busyAction, setBusyAction] = useState(null);
    const [error, setError] = useState(null);

    const refresh = useCallback(async () => {
        if (!workspaceId) {
            setVersions([]);
            return;
        }
        try {
            setError(null);
            setVersions(normalizeVersions(await steamWorkshopCoverService.listVersions(workspaceId)));
        } catch (requestError) {
            setError(requestError);
        }
    }, [workspaceId]);

    useEffect(() => {
        setSelectedVersionId(currentVersionId);
        setEditingParentVersionId(currentVersionId);
    }, [currentVersionId, workspaceId]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const saveVersion = useCallback(async ({ pngDataUrl, canvas }) => {
        if (!workspaceId) return null;
        setBusyAction('save');
        setError(null);
        try {
            const created = await steamWorkshopCoverService.createVersion(workspaceId, {
                pngDataUrl,
                canvas,
                parentVersionId: editingParentVersionId,
            });
            setEditingParentVersionId(created.version_id);
            await refresh();
            return created;
        } catch (requestError) {
            setError(requestError);
            return null;
        } finally {
            setBusyAction(null);
        }
    }, [editingParentVersionId, refresh, workspaceId]);

    const loadVersion = useCallback(async (versionId) => {
        setBusyAction(`load:${versionId}`);
        setError(null);
        try {
            const version = await steamWorkshopCoverService.getVersion(versionId);
            await onLoadCanvas(version.canvas);
            setEditingParentVersionId(version.version_id);
        } catch (requestError) {
            setError(requestError);
        } finally {
            setBusyAction(null);
        }
    }, [onLoadCanvas]);

    const selectVersion = useCallback(async (versionId) => {
        if (!workspaceId) return;
        setBusyAction(`select:${versionId}`);
        setError(null);
        try {
            await steamWorkshopCoverService.selectVersion(workspaceId, versionId);
            setSelectedVersionId(versionId);
            await refresh();
        } catch (requestError) {
            setError(requestError);
        } finally {
            setBusyAction(null);
        }
    }, [refresh, workspaceId]);

    return {
        versions,
        selectedVersionId,
        editingParentVersionId,
        busyAction,
        error,
        refresh,
        saveVersion,
        loadVersion,
        selectVersion,
    };
};

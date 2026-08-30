import { useCallback, useState } from 'react';

import api from '../../utils/api';
import { getErrorMessage } from './modArchiveModel';

export const useRemoveModArchive = ({ projectId, projectName, onRemoved, t }) => {
    const [opened, setOpened] = useState(false);
    const [removing, setRemoving] = useState(false);
    const [error, setError] = useState(null);

    const open = useCallback(() => {
        setError(null);
        setOpened(true);
    }, []);

    const close = useCallback(() => {
        if (!removing) setOpened(false);
    }, [removing]);

    const remove = useCallback(async () => {
        if (!projectId || !projectName || removing) return false;
        setRemoving(true);
        setError(null);
        try {
            const response = await api.delete(
                `/api/context/projects/${encodeURIComponent(projectId)}/archive`,
                { data: { project_name: projectName, approved: true } },
            );
            setOpened(false);
            await onRemoved?.(response.data);
            return true;
        } catch (requestError) {
            setError(getErrorMessage(
                requestError,
                t('mod_archive.release.removal.error'),
            ));
            return false;
        } finally {
            setRemoving(false);
        }
    }, [onRemoved, projectId, projectName, removing, t]);

    return { opened, removing, error, open, close, remove };
};

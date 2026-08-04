import { useCallback, useEffect, useState } from 'react';

import api from '../../../utils/api';

const encode = (value) => encodeURIComponent(String(value || ''));
const isTreeV2 = (tree) => Boolean(
    tree
    && tree.tree_id
    && tree.project_id
    && String(tree.schema_version || '').startsWith('context-tree-v2'),
);

export const contextTreeV2ArchivePath = (projectId, mode) => (
    `/api/context/tree-v2/projects/${encode(projectId)}/${mode === 'published' ? 'latest-release' : 'latest'}`
);

export const useContextTreeV2Archive = (projectId, mode = 'published') => {
    const [state, setState] = useState({ phase: projectId ? 'loading' : 'idle', tree: null, error: null });
    const refresh = useCallback(async () => {
        if (!projectId) {
            setState({ phase: 'idle', tree: null, error: null });
            return null;
        }
        setState((current) => ({ ...current, phase: 'loading', error: null }));
        try {
            const response = await api.get(contextTreeV2ArchivePath(projectId, mode));
            const tree = response?.data || response;
            if (!isTreeV2(tree)) {
                setState({ phase: 'empty', tree: null, error: null });
                return null;
            }
            setState({ phase: 'ready', tree, error: null });
            return tree;
        } catch (error) {
            if (error?.response?.status === 404) {
                setState({ phase: 'empty', tree: null, error: null });
                return null;
            }
            setState({ phase: 'error', tree: null, error: error?.message || 'context_tree_v2_load_failed' });
            return null;
        }
    }, [mode, projectId]);

    useEffect(() => { refresh(); }, [refresh]);
    return { ...state, refresh };
};

export default useContextTreeV2Archive;

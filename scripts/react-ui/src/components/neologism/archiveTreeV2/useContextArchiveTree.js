import { useCallback, useEffect, useRef, useState } from 'react';

import {
    createEmptyArchiveTree,
    normalizeArchiveTree,
} from './contextArchiveTreeModel';
import {
    createGroup,
    createStory,
    deleteGroup,
    deleteStory,
    moveFragment,
    renameGroup,
    renameStory,
    reorderFragment,
    serializeArchiveTree,
    setFragmentDisposition,
} from './contextArchiveTreeController';

const initialState = (initialTree) => ({
    phase: initialTree ? (normalizeArchiveTree(initialTree).available ? 'ready' : 'empty') : 'empty',
    tree: initialTree ? normalizeArchiveTree(initialTree) : createEmptyArchiveTree(),
    dirty: false,
    saving: false,
    error: null,
});

const unwrapLoadedTree = (value) => value?.tree
    || value?.context_tree_v2
    || value?.context_tree
    || value?.data?.tree
    || value;

export const useContextArchiveTree = ({
    initialTree = null,
    adapter = null,
    enabled = true,
    projectId,
    releaseId,
    draftId,
    mode = 'published',
} = {}) => {
    const [state, setState] = useState(() => initialState(initialTree));
    const requestVersionRef = useRef(0);
    const initialTreeRef = useRef(initialTree);

    useEffect(() => {
        if (initialTreeRef.current === initialTree) return;
        initialTreeRef.current = initialTree;
        const tree = initialTree ? normalizeArchiveTree(initialTree) : createEmptyArchiveTree();
        setState({
            phase: tree.available ? 'ready' : 'empty',
            tree,
            dirty: false,
            saving: false,
            error: null,
        });
    }, [initialTree]);

    const load = useCallback(async () => {
        if (!enabled || !adapter?.load) return null;
        const requestVersion = requestVersionRef.current + 1;
        requestVersionRef.current = requestVersion;
        setState((current) => ({ ...current, phase: 'loading', error: null }));
        try {
            const response = await adapter.load({ projectId, releaseId, draftId, mode });
            const tree = normalizeArchiveTree(unwrapLoadedTree(response));
            if (requestVersionRef.current !== requestVersion) return tree;
            setState({
                phase: tree.available ? 'ready' : 'empty',
                tree,
                dirty: false,
                saving: false,
                error: null,
            });
            return tree;
        } catch (error) {
            if (requestVersionRef.current !== requestVersion) return null;
            setState((current) => ({
                ...current,
                phase: 'error',
                error: error?.message || 'context_tree_load_failed',
            }));
            return null;
        }
    }, [adapter, draftId, enabled, mode, projectId, releaseId]);

    useEffect(() => {
        if (adapter?.load && enabled) load();
    }, [adapter, enabled, load]);

    const apply = useCallback((operation) => {
        setState((current) => ({
            ...current,
            tree: operation(current.tree),
            phase: 'ready',
            dirty: true,
            error: null,
        }));
    }, []);

    const save = useCallback(async () => {
        if (!adapter?.save || !state.dirty || state.saving) return false;
        setState((current) => ({ ...current, saving: true, error: null }));
        try {
            const response = await adapter.save({
                projectId,
                releaseId,
                draftId,
                mode,
                tree: serializeArchiveTree(state.tree),
            });
            const responseTree = unwrapLoadedTree(response);
            const nextTree = responseTree && normalizeArchiveTree(responseTree).available
                ? normalizeArchiveTree(responseTree)
                : state.tree;
            setState((current) => ({ ...current, tree: nextTree, dirty: false, saving: false }));
            return true;
        } catch (error) {
            setState((current) => ({
                ...current,
                saving: false,
                error: error?.message || 'context_tree_save_failed',
            }));
            return false;
        }
    }, [adapter, draftId, mode, projectId, releaseId, state.dirty, state.saving, state.tree]);

    const reset = useCallback(() => {
        const tree = initialTree ? normalizeArchiveTree(initialTree) : createEmptyArchiveTree();
        setState({
            phase: tree.available ? 'ready' : 'empty',
            tree,
            dirty: false,
            saving: false,
            error: null,
        });
    }, [initialTree]);

    const actions = {
        createStory: (options) => apply((tree) => createStory(tree, options)),
        renameStory: (storyId, label) => apply((tree) => renameStory(tree, storyId, label)),
        deleteStory: (storyId) => apply((tree) => deleteStory(tree, storyId)),
        createGroup: (options) => apply((tree) => createGroup(tree, options)),
        renameGroup: (groupId, label) => apply((tree) => renameGroup(tree, groupId, label)),
        deleteGroup: (groupId) => apply((tree) => deleteGroup(tree, groupId)),
        moveFragment: (options) => apply((tree) => moveFragment(tree, options)),
        reorderFragment: (options) => apply((tree) => reorderFragment(tree, options)),
        setFragmentDisposition: (fragmentId, route, options) => apply((tree) => (
            setFragmentDisposition(tree, fragmentId, route, options)
        )),
    };

    return {
        ...state,
        canSave: Boolean(adapter?.save),
        load,
        save,
        reset,
        ...actions,
    };
};

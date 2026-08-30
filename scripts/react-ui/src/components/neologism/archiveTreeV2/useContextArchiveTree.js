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
    pendingOperations: [],
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
            pendingOperations: [],
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
                pendingOperations: [],
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

    const apply = useCallback((operation, operationBuilder) => {
        setState((current) => {
            const tree = operation(current.tree);
            const built = operationBuilder?.(current.tree, tree) || [];
            const operations = Array.isArray(built) ? built : [built];
            return {
                ...current,
                tree,
                phase: 'ready',
                dirty: true,
                pendingOperations: [...current.pendingOperations, ...operations.filter(Boolean)],
                error: null,
            };
        });
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
                operations: state.pendingOperations,
            });
            const responseTree = unwrapLoadedTree(response);
            const nextTree = responseTree && normalizeArchiveTree(responseTree).available
                ? normalizeArchiveTree(responseTree)
                : state.tree;
            setState((current) => ({
                ...current, tree: nextTree, dirty: false, saving: false, pendingOperations: [],
            }));
            return true;
        } catch (error) {
            setState((current) => ({
                ...current,
                saving: false,
                error: error?.message || 'context_tree_save_failed',
            }));
            return false;
        }
    }, [adapter, draftId, mode, projectId, releaseId, state.dirty, state.pendingOperations, state.saving, state.tree]);

    const reset = useCallback(() => {
        const tree = initialTree ? normalizeArchiveTree(initialTree) : createEmptyArchiveTree();
        setState({
            phase: tree.available ? 'ready' : 'empty',
            tree,
            dirty: false,
            pendingOperations: [],
            saving: false,
            error: null,
        });
    }, [initialTree]);

    const actions = {
        createStory: (options) => apply(
            (tree) => createStory(tree, options),
            (before, after) => {
                const item = after.stories.find((story) => !before.stories.some((old) => old.id === story.id));
                return item && { operation: 'create_story', story_id: item.id, new_name: item.label };
            },
        ),
        renameStory: (storyId, label) => apply(
            (tree) => renameStory(tree, storyId, label),
            () => ({ operation: 'rename_story', story_id: storyId, new_name: label }),
        ),
        deleteStory: (storyId) => apply(
            (tree) => deleteStory(tree, storyId),
            () => ({ operation: 'delete_story', story_id: storyId }),
        ),
        createGroup: (options) => apply(
            (tree) => createGroup(tree, options),
            (before, after) => {
                const item = after.groups.find((group) => !before.groups.some((old) => old.id === group.id));
                return item && { operation: 'create_group', group_id: item.id, story_id: item.storyId, new_name: item.label };
            },
        ),
        renameGroup: (groupId, label) => apply(
            (tree) => renameGroup(tree, groupId, label),
            () => ({ operation: 'rename_group', group_id: groupId, new_name: label }),
        ),
        deleteGroup: (groupId) => apply(
            (tree) => deleteGroup(tree, groupId),
            () => ({ operation: 'delete_group', group_id: groupId }),
        ),
        moveFragment: (options) => apply(
            (tree) => moveFragment(tree, options),
            () => ({
                operation: 'move_fragment', fragment_id: options.fragmentId,
                target_group_id: options.targetGroupId,
                before_fragment_id: options.overFragmentId || undefined,
            }),
        ),
        reorderFragment: (options) => apply(
            (tree) => reorderFragment(tree, options),
            () => ({
                operation: 'reorder_fragment', group_id: options.groupId,
                fragment_id: options.fragmentId,
                before_fragment_id: options.overFragmentId || undefined,
            }),
        ),
        setFragmentDisposition: (fragmentId, route, options) => apply(
            (tree) => setFragmentDisposition(tree, fragmentId, route, options),
            (before, after) => (before.fragments[fragmentId]?.unitIds || []).map((unitId) => ({
                operation: 'set_unit_route',
                local_unit_id: unitId,
                route: route === 'unresolved' ? 'no_context' : route,
                fragment_ids: route === 'narrative'
                    ? Object.values(after.fragments)
                        .filter((fragment) => fragment.route === 'narrative' && fragment.unitIds.includes(unitId))
                        .map((fragment) => fragment.id)
                    : [],
            })),
        ),
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

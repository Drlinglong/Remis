import {
    TREE_ROUTE,
    getGroupById,
    normalizeArchiveTree,
} from './contextArchiveTreeModel';

const asLabel = (value, fallback) => String(value || '').trim() || fallback;

const slugify = (value) => String(value || '')
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    || 'item';

const unique = (items) => [...new Set(items.filter(Boolean))];

const cloneTree = (tree) => ({
    ...tree,
    stories: (tree?.stories || []).map((story) => ({ ...story, groupIds: [...(story.groupIds || [])] })),
    groups: (tree?.groups || []).map((group) => ({ ...group, fragmentIds: [...(group.fragmentIds || [])] })),
    fragments: Object.fromEntries(Object.entries(tree?.fragments || {}).map(([id, fragment]) => [
        id,
        { ...fragment, unitIds: [...(fragment.unitIds || [])], evidenceIds: [...(fragment.evidenceIds || [])] },
    ])),
    units: { ...(tree?.units || {}) },
    referenceAssets: [...(tree?.referenceAssets || [])],
    unresolvedFragmentIds: [...(tree?.unresolvedFragmentIds || [])],
});

const makeId = (collection, prefix, label, requestedId) => {
    const base = String(requestedId || `${prefix}-${slugify(label)}`);
    const used = new Set(collection.map((item) => item.id));
    if (!used.has(base)) return base;
    let suffix = 2;
    while (used.has(`${base}-${suffix}`)) suffix += 1;
    return `${base}-${suffix}`;
};

const findGroupContaining = (tree, fragmentId) => tree.groups.find((group) => (
    group.fragmentIds.includes(fragmentId)
));

const removeFragmentFromGroups = (tree, fragmentId) => {
    tree.groups.forEach((group) => {
        group.fragmentIds = group.fragmentIds.filter((id) => id !== fragmentId);
    });
};

const removeReferenceAssetForFragment = (tree, fragmentId) => {
    tree.referenceAssets = tree.referenceAssets.filter((asset) => (
        asset.fragmentId !== fragmentId && asset.id !== fragmentId
    ));
};

const addAt = (items, value, { index, overId } = {}) => {
    const next = [...items];
    const targetIndex = overId
        ? next.indexOf(overId)
        : Number.isInteger(index) ? Math.max(0, Math.min(index, next.length)) : next.length;
    next.splice(targetIndex < 0 ? next.length : targetIndex, 0, value);
    return next;
};

export const createStory = (tree, { id, label, summary = '' } = {}) => {
    const next = cloneTree(tree);
    const storyId = makeId(next.stories, 'story', label, id);
    next.stories.push({ id: storyId, label: asLabel(label, storyId), summary, groupIds: [] });
    return next;
};

export const renameStory = (tree, storyId, label) => {
    const next = cloneTree(tree);
    const story = next.stories.find((item) => item.id === storyId);
    if (story) story.label = asLabel(label, story.label);
    return next;
};

export const deleteStory = (tree, storyId) => {
    const next = cloneTree(tree);
    const story = next.stories.find((item) => item.id === storyId);
    if (!story) return next;
    const groupIds = new Set(story.groupIds);
    const orphanedFragments = next.groups
        .filter((group) => groupIds.has(group.id) || group.storyId === storyId)
        .flatMap((group) => group.fragmentIds);
    next.stories = next.stories.filter((item) => item.id !== storyId);
    next.groups = next.groups.filter((group) => !groupIds.has(group.id) && group.storyId !== storyId);
    next.unresolvedFragmentIds = unique([...next.unresolvedFragmentIds, ...orphanedFragments]);
    return next;
};

export const createGroup = (tree, { storyId, id, label, summary = '' } = {}) => {
    const next = cloneTree(tree);
    const story = next.stories.find((item) => item.id === storyId);
    if (!story) return next;
    const groupId = makeId(next.groups, 'group', label, id);
    next.groups.push({ id: groupId, storyId, label: asLabel(label, groupId), summary, fragmentIds: [] });
    story.groupIds = unique([...story.groupIds, groupId]);
    return next;
};

export const renameGroup = (tree, groupId, label) => {
    const next = cloneTree(tree);
    const group = getGroupById(next, groupId);
    if (group) group.label = asLabel(label, group.label);
    return next;
};

export const deleteGroup = (tree, groupId) => {
    const next = cloneTree(tree);
    const group = getGroupById(next, groupId);
    if (!group) return next;
    next.groups = next.groups.filter((item) => item.id !== groupId);
    next.stories = next.stories.map((story) => ({
        ...story,
        groupIds: story.groupIds.filter((id) => id !== groupId),
    }));
    next.unresolvedFragmentIds = unique([...next.unresolvedFragmentIds, ...group.fragmentIds]);
    return next;
};

export const moveFragment = (tree, {
    fragmentId,
    targetGroupId,
    overFragmentId = null,
    index,
} = {}) => {
    const next = cloneTree(tree);
    const fragment = next.fragments[fragmentId];
    const targetGroup = getGroupById(next, targetGroupId);
    if (!fragment || !targetGroup) return next;
    removeFragmentFromGroups(next, fragmentId);
    targetGroup.fragmentIds = addAt(targetGroup.fragmentIds, fragmentId, {
        index,
        overId: overFragmentId === fragmentId ? null : overFragmentId,
    });
    fragment.route = TREE_ROUTE.NARRATIVE;
    next.unresolvedFragmentIds = next.unresolvedFragmentIds.filter((id) => id !== fragmentId);
    removeReferenceAssetForFragment(next, fragmentId);
    return next;
};

export const reorderFragment = (tree, {
    fragmentId,
    groupId,
    overFragmentId = null,
    index,
} = {}) => moveFragment(tree, {
    fragmentId,
    targetGroupId: groupId,
    overFragmentId,
    index,
});

export const setFragmentDisposition = (tree, fragmentId, route, { targetGroupId, index } = {}) => {
    const next = cloneTree(tree);
    const fragment = next.fragments[fragmentId];
    if (!fragment) return next;
    removeFragmentFromGroups(next, fragmentId);
    removeReferenceAssetForFragment(next, fragmentId);
    next.unresolvedFragmentIds = next.unresolvedFragmentIds.filter((id) => id !== fragmentId);
    fragment.route = Object.values(TREE_ROUTE).includes(route) ? route : TREE_ROUTE.UNRESOLVED;
    if (fragment.route === TREE_ROUTE.NARRATIVE && targetGroupId) {
        const targetGroup = getGroupById(next, targetGroupId);
        if (targetGroup) targetGroup.fragmentIds = addAt(targetGroup.fragmentIds, fragmentId, { index });
    } else if (fragment.route === TREE_ROUTE.REFERENCE_ASSET) {
        next.referenceAssets.push({
            id: fragment.id,
            fragmentId: fragment.id,
            label: fragment.label,
            summary: fragment.summary,
            tier: fragment.tier,
            unitIds: [...fragment.unitIds],
            evidenceIds: [...fragment.evidenceIds],
            sourceRefs: [...(fragment.sourceRefs || [])],
            metadata: { ...fragment.metadata },
        });
    } else {
        next.unresolvedFragmentIds = unique([...next.unresolvedFragmentIds, fragmentId]);
    }
    return next;
};

export const assignFragmentToGroup = (tree, fragmentId, targetGroupId, options = {}) => moveFragment(tree, {
    ...options,
    fragmentId,
    targetGroupId,
});

export const serializeArchiveTree = (tree) => ({
    schema_version: tree.version || 'context-tree-v2',
    project_id: tree.projectId || null,
    release_id: tree.releaseId || null,
    project_summary: tree.projectSummary || '',
    stories: tree.stories.map((story) => ({
        story_id: story.id,
        label: story.label,
        group_ids: [...story.groupIds],
    })),
    groups: tree.groups.map((group) => ({
        group_id: group.id,
        story_id: group.storyId,
        label: group.label,
        fragment_ids: [...group.fragmentIds],
    })),
    fragments: Object.values(tree.fragments).map((fragment) => ({
        fragment_id: fragment.id,
        label: fragment.label,
        summary: fragment.summary,
        unit_ids: [...fragment.unitIds],
        route: fragment.route,
        tier: fragment.tier,
    })),
    reference_assets: tree.referenceAssets.map((asset) => ({
        asset_id: asset.id,
        fragment_id: asset.fragmentId,
        label: asset.label,
        summary: asset.summary,
        tier: asset.tier,
        unit_ids: [...(asset.unitIds || [])],
    })),
    unresolved_fragment_ids: [...tree.unresolvedFragmentIds],
});

export const applyTreeDraft = (tree, operation) => normalizeArchiveTree(operation(cloneTree(tree)));

export const findFragmentGroup = (tree, fragmentId) => findGroupContaining(tree, fragmentId);

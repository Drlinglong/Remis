export const TREE_ROUTE = Object.freeze({
    NARRATIVE: 'narrative',
    REFERENCE_ASSET: 'reference_asset',
    UNRESOLVED: 'unresolved',
    NO_CONTEXT: 'no_context',
});

export const REFERENCE_ASSET_TIERS = Object.freeze(['A', 'B', 'C']);
export const UNRESOLVED_STORY_ID = 'story-unresolved';
export const UNRESOLVED_GROUP_ID = 'group-unresolved';

const TIER_ORDER = Object.freeze({ A: 0, B: 1, C: 2 });
const ROUTE_VALUES = new Set(Object.values(TREE_ROUTE));

const asObject = (value) => (
    value && typeof value === 'object' && !Array.isArray(value) ? value : {}
);

const firstValue = (...values) => values.find((value) => (
    value !== undefined && value !== null && value !== ''
));

const asList = (value) => {
    if (Array.isArray(value)) return value;
    if (value && typeof value === 'object') {
        return Object.entries(value).map(([key, item]) => (
            item && typeof item === 'object' && !Array.isArray(item)
                ? { ...item, id: item.id || item.key || key }
                : { id: key, value: item }
        ));
    }
    return [];
};

const asId = (value) => {
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    if (value && typeof value === 'object') {
        return firstValue(
            value.id,
            value.unit_id,
            value.local_unit_id,
            value.fragment_id,
            value.story_id,
            value.group_id,
            value.asset_id,
            value.reference_asset_id,
            value.key,
        );
    }
    return null;
};

const asIdList = (value) => [...new Set(asList(value)
    .map(asId)
    .filter(Boolean))];

const slugify = (value) => String(value || '')
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    || 'item';

const normalizeTier = (value) => {
    const normalized = String(value || '').trim().toLocaleUpperCase();
    if (normalized === 'CORE' || normalized === 'TIER_A') return 'A';
    if (normalized === 'SECONDARY' || normalized === 'TIER_B') return 'B';
    if (normalized === 'INCIDENTAL' || normalized === 'TIER_C') return 'C';
    return REFERENCE_ASSET_TIERS.includes(normalized) ? normalized : 'C';
};

const normalizeRoute = (value) => {
    const normalized = String(value || '').trim().toLocaleLowerCase();
    if (ROUTE_VALUES.has(normalized)) return normalized;
    if (['reference', 'asset', 'reference-asset', 'reference_asset_route'].includes(normalized)) {
        return TREE_ROUTE.REFERENCE_ASSET;
    }
    if (['unresolved', 'unknown', 'repair_required', 'repair-required'].includes(normalized)) {
        return TREE_ROUTE.UNRESOLVED;
    }
    if (['none', 'no-context', 'no context'].includes(normalized)) return TREE_ROUTE.NO_CONTEXT;
    return TREE_ROUTE.NARRATIVE;
};

const normalizeRawRoute = (raw = {}) => {
    if (raw.unresolved === true || raw.is_unresolved === true) return TREE_ROUTE.UNRESOLVED;
    if (raw.reference_asset === true || raw.is_reference_asset === true) {
        return TREE_ROUTE.REFERENCE_ASSET;
    }
    return normalizeRoute(firstValue(raw.route, raw.unit_route, raw.disposition, raw.role));
};

const getLabel = (raw, fallback) => String(firstValue(
    raw.label,
    raw.title,
    raw.name,
    raw.display_name,
    raw.fragment_label,
    raw.group_label,
    raw.story_label,
    fallback,
) || fallback);

const getSummary = (raw, fallback = '') => String(firstValue(
    raw.summary,
    raw.short_summary,
    raw.description,
    raw.fragment_summary,
    fallback,
) || '');

const unwrapTreePayload = (payload) => {
    const value = asObject(payload);
    return asObject(firstValue(
        value.context_tree_v2,
        value.context_tree,
        value.archive_tree,
        value.tree,
        value.data?.context_tree_v2,
        value.data?.context_tree,
        value.data?.tree,
        payload,
    ));
};

const normalizeUnit = (raw, index) => {
    const id = asId(raw) || `unit-${index + 1}`;
    const metadata = asObject(raw?.metadata);
    return {
        id,
        label: getLabel(raw || {}, id),
        sourceRef: firstValue(raw?.source_ref, raw?.sourceRef, raw?.source_item_ref, metadata.source_ref) || '',
        route: normalizeRawRoute(raw || {}),
        summary: getSummary(raw || {}),
        sourceText: String(firstValue(raw?.source_text, raw?.source, raw?.text, raw?.content) || ''),
        metadata,
    };
};

const normalizeFragment = (raw, index, forcedRoute = null) => {
    const value = asObject(raw);
    const metadata = asObject(value.metadata);
    const id = asId(value) || `fragment-${index + 1}`;
    const route = forcedRoute || normalizeRawRoute(value);
    const coverage = asObject(firstValue(value.coverage, metadata.coverage));
    return {
        id,
        label: getLabel(value, id),
        summary: getSummary(value, id),
        unitIds: asIdList(firstValue(
            value.unit_ids,
            value.unitIds,
            value.local_unit_ids,
            value.localUnitIds,
            value.units,
            value.local_units,
        )),
        route,
        tier: normalizeTier(firstValue(value.tier, value.level, metadata.tier)),
        coverage,
        evidenceIds: asIdList(firstValue(
            value.evidence_unit_ids,
            value.evidenceIds,
            value.evidence_ids,
            value.evidence,
            metadata.evidence_unit_ids,
        )),
        sourceRefs: asList(firstValue(value.source_refs, value.sourceRefs, metadata.source_refs))
            .map((item) => String(asId(item) || item || '').trim())
            .filter(Boolean),
        metadata,
    };
};

const normalizeReferenceAsset = (raw, index) => {
    const value = asObject(raw);
    const metadata = asObject(value.metadata);
    const id = firstValue(value.asset_id, value.reference_asset_id, value.entity_id, asId(value))
        || `reference-asset-${index + 1}`;
    return {
        id: String(id),
        fragmentId: firstValue(value.fragment_id, value.local_fragment_id) || null,
        label: getLabel(value, String(id)),
        summary: getSummary(value),
        tier: normalizeTier(firstValue(value.tier, value.level, metadata.tier)),
        unitIds: asIdList(firstValue(value.unit_ids, value.unitIds, value.local_unit_ids, value.localUnitIds, value.units)),
        evidenceIds: asIdList(firstValue(value.evidence_unit_ids, value.evidenceIds, value.evidence_ids, value.evidence)),
        sourceRefs: asList(firstValue(value.source_refs, value.sourceRefs))
            .map((item) => String(asId(item) || item || '').trim())
            .filter(Boolean),
        metadata,
    };
};

const normalizeStory = (raw, index) => {
    const value = asObject(raw);
    const id = firstValue(value.story_id, value.storyId, asId(value))
        || `story-${slugify(getLabel(value, index + 1))}`;
    return {
        id: String(id),
        label: getLabel(value, String(id)),
        summary: getSummary(value),
        groupIds: asIdList(firstValue(value.group_ids, value.groupIds, value.groups)),
    };
};

const normalizeGroup = (raw, index) => {
    const value = asObject(raw);
    const id = firstValue(value.group_id, value.groupId, asId(value))
        || `group-${slugify(getLabel(value, index + 1))}`;
    return {
        id: String(id),
        storyId: firstValue(value.story_id, value.storyId, value.parent_story_id, value.parentStoryId) || null,
        label: getLabel(value, String(id)),
        summary: getSummary(value),
        fragmentIds: asIdList(firstValue(
            value.fragment_ids,
            value.fragmentIds,
            value.local_fragment_ids,
            value.localFragmentIds,
            value.fragments,
        )),
    };
};

const addFragment = (map, raw, index, forcedRoute = null) => {
    const fragment = normalizeFragment(raw, index, forcedRoute);
    if (!map[fragment.id]) map[fragment.id] = fragment;
    return fragment.id;
};

const withUnique = (items) => [...new Set(items.filter(Boolean))];

const stableLabelCompare = (left, right) => (
    left.label.normalize('NFKC').replace(/[^\p{L}\p{N}]+/gu, '').toLocaleLowerCase()
        .localeCompare(right.label.normalize('NFKC').replace(/[^\p{L}\p{N}]+/gu, '').toLocaleLowerCase())
        || left.id.localeCompare(right.id)
);

export const sortReferenceAssets = (assets = []) => [...assets].sort((left, right) => (
    (TIER_ORDER[left.tier] ?? TIER_ORDER.C) - (TIER_ORDER[right.tier] ?? TIER_ORDER.C)
        || stableLabelCompare(left, right)
));

export const groupReferenceAssetsByTier = (assets = []) => REFERENCE_ASSET_TIERS.map((tier) => ({
    tier,
    openByDefault: tier !== 'C',
    assets: sortReferenceAssets(assets.filter((asset) => asset.tier === tier)),
})).filter((group) => group.assets.length > 0);

export const getTreeUnitOptions = (tree) => Object.values(tree?.units || {})
    .filter((unit) => unit.route === TREE_ROUTE.NARRATIVE || unit.route === TREE_ROUTE.UNRESOLVED)
    .sort((left, right) => left.label.localeCompare(right.label, undefined, { sensitivity: 'base' })
        || left.id.localeCompare(right.id));

export const getFragmentById = (tree, fragmentId) => tree?.fragments?.[fragmentId] || null;

export const getGroupById = (tree, groupId) => tree?.groups?.find((group) => group.id === groupId) || null;

export const buildNarrativeUnitPreview = (tree, unitId) => {
    if (!tree || !unitId) return null;
    const unit = tree.units?.[unitId] || { id: unitId, label: unitId, route: TREE_ROUTE.NARRATIVE };
    const groups = [];
    tree.stories.forEach((story) => {
        story.groupIds.forEach((groupId) => {
            const group = getGroupById(tree, groupId);
            if (!group || !group.fragmentIds.some((fragmentId) => (
                tree.fragments[fragmentId]?.unitIds.includes(unitId)
            ))) return;
            const fragments = group.fragmentIds
                .map((fragmentId) => tree.fragments[fragmentId])
                .filter((fragment) => fragment && fragment.route === TREE_ROUTE.NARRATIVE)
                .map((fragment, order) => ({
                    id: fragment.id,
                    label: fragment.label,
                    summary: fragment.summary,
                    order,
                }));
            groups.push({
                storyId: story.id,
                storyLabel: story.label,
                groupId: group.id,
                groupLabel: group.label,
                fragments,
                bullets: fragments.map((fragment) => fragment.summary),
            });
        });
    });
    return {
        unit,
        unitId,
        route: unit.route,
        projectSummary: tree.projectSummary,
        groups,
        hasEventContext: groups.length > 0 && unit.route === TREE_ROUTE.NARRATIVE,
    };
};

export const getFirstNarrativeUnitId = (tree) => getTreeUnitOptions(tree)[0]?.id || null;

export const normalizeArchiveTree = (payload) => {
    const raw = unwrapTreePayload(payload);
    const rawStories = asList(firstValue(raw.stories, raw.story_catalog, raw.parent_stories));
    const nestedGroups = [];
    rawStories.forEach((story) => {
        const storyId = firstValue(story?.story_id, story?.storyId, asId(story));
        asList(story?.groups).forEach((group) => {
            nestedGroups.push({ ...asObject(group), story_id: group.story_id || storyId });
        });
    });
    const rawGroups = [
        ...asList(firstValue(raw.groups, raw.event_groups, raw.eventGroups)),
        ...nestedGroups,
    ];
    const fragments = {};
    const fragmentSources = asList(firstValue(raw.fragments, raw.local_fragments, raw.localFragments));
    fragmentSources.forEach((fragment, index) => addFragment(fragments, fragment, index));
    rawGroups.forEach((group) => {
        asList(group?.fragments).forEach((fragment, index) => addFragment(fragments, fragment, index));
    });
    asList(raw.unresolved_fragments || raw.unresolved).forEach((fragment, index) => {
        addFragment(fragments, fragment, fragmentSources.length + index, TREE_ROUTE.UNRESOLVED);
    });
    const rawReferenceAssets = asList(firstValue(raw.reference_assets, raw.referenceAssets));
    rawReferenceAssets.forEach((asset, index) => {
        const fragmentId = firstValue(asset?.fragment_id, asset?.local_fragment_id);
        if (fragmentId && !fragments[fragmentId]) addFragment(fragments, asset, index, TREE_ROUTE.REFERENCE_ASSET);
    });

    const groupsById = new Map();
    rawGroups.forEach((group, index) => {
        const normalized = normalizeGroup(group, index);
        const nestedFragmentIds = asList(group?.fragments)
            .map((fragment, fragmentIndex) => addFragment(fragments, fragment, fragmentIndex));
        normalized.fragmentIds = withUnique([...normalized.fragmentIds, ...nestedFragmentIds]);
        if (!groupsById.has(normalized.id)) groupsById.set(normalized.id, normalized);
    });

    const storiesById = new Map();
    rawStories.forEach((story, index) => {
        const normalized = normalizeStory(story, index);
        if (!storiesById.has(normalized.id)) storiesById.set(normalized.id, normalized);
    });
    groupsById.forEach((group) => {
        if (!group.storyId && storiesById.size === 1) group.storyId = [...storiesById.keys()][0];
        if (group.storyId && !storiesById.has(group.storyId)) {
            storiesById.set(group.storyId, {
                id: group.storyId,
                label: group.storyId,
                summary: '',
                groupIds: [],
            });
        }
    });
    if (groupsById.size > 0 && storiesById.size === 0) {
        storiesById.set('story-main', {
            id: 'story-main',
            label: getLabel(raw, 'Story'),
            summary: '',
            groupIds: [],
        });
        groupsById.forEach((group) => { group.storyId = 'story-main'; });
    }
    groupsById.forEach((group) => {
        const story = storiesById.get(group.storyId);
        if (story && !story.groupIds.includes(group.id)) story.groupIds.push(group.id);
    });

    const memberIds = new Set();
    groupsById.forEach((group) => {
        group.fragmentIds = withUnique(group.fragmentIds).filter((fragmentId) => {
            const fragment = fragments[fragmentId];
            if (!fragment || fragment.route !== TREE_ROUTE.NARRATIVE || memberIds.has(fragmentId)) return false;
            memberIds.add(fragmentId);
            return true;
        });
    });

    const unresolvedIds = new Set(asIdList(raw.unresolved_fragment_ids || raw.unresolvedFragmentIds));
    Object.values(fragments).forEach((fragment) => {
        if (fragment.route === TREE_ROUTE.REFERENCE_ASSET) return;
        if (fragment.route === TREE_ROUTE.UNRESOLVED || !memberIds.has(fragment.id)) unresolvedIds.add(fragment.id);
    });

    const referenceAssets = rawReferenceAssets.map(normalizeReferenceAsset);
    Object.values(fragments).forEach((fragment) => {
        if (fragment.route !== TREE_ROUTE.REFERENCE_ASSET) return;
        referenceAssets.push({
            id: fragment.id,
            fragmentId: fragment.id,
            label: fragment.label,
            summary: fragment.summary,
            tier: fragment.tier,
            unitIds: fragment.unitIds,
            evidenceIds: fragment.evidenceIds,
            sourceRefs: fragment.sourceRefs,
            metadata: fragment.metadata,
        });
    });
    const uniqueAssets = [...new Map(referenceAssets.map((asset) => [asset.id, asset])).values()];
    const rawUnits = asList(firstValue(raw.units, raw.local_units, raw.localUnits));
    const units = Object.fromEntries(rawUnits.map((unit, index) => {
        const normalized = normalizeUnit(unit, index);
        return [normalized.id, normalized];
    }));
    Object.values(fragments).forEach((fragment) => fragment.unitIds.forEach((unitId) => {
        if (!units[unitId]) units[unitId] = normalizeUnit({ id: unitId, label: unitId }, Object.keys(units).length);
    }));

    const available = Boolean(
        payload && (rawStories.length || rawGroups.length || fragmentSources.length
            || rawReferenceAssets.length || raw.unresolved_fragments || raw.unresolved_fragment_ids
            || raw.schema_version || raw.version),
    );
    return {
        available,
        version: String(firstValue(raw.schema_version, raw.version, 'context-tree-v2')),
        projectId: firstValue(raw.project_id, raw.projectId, null),
        releaseId: firstValue(raw.release_id, raw.releaseId, null),
        title: getLabel(raw, firstValue(raw.project_title, raw.project_name, 'Context archive tree')),
        projectSummary: String(firstValue(raw.project_summary, raw.summary, '') || ''),
        stories: [...storiesById.values()],
        groups: [...groupsById.values()],
        fragments,
        units,
        referenceAssets: sortReferenceAssets(uniqueAssets),
        unresolvedFragmentIds: [...unresolvedIds].filter((id) => Boolean(fragments[id])),
    };
};

export const createEmptyArchiveTree = () => normalizeArchiveTree(null);

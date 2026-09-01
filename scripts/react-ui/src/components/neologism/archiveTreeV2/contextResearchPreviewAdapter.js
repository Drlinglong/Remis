const unique = (values = []) => [...new Set(values.filter(Boolean))];

const evidenceIds = (item = {}) => unique((item.evidence || [])
    .flatMap((reference) => reference.source_item_ids || []));

const sourceRefs = (item = {}) => evidenceIds(item);

const archiveLabel = (item = {}) => {
    const prefix = String(item.summary || '').split(/[：:]/, 1)[0].trim();
    return prefix || item.narrative_id || '档案叙事';
};

const unresolvedLabel = (item = {}) => {
    const value = String(item.unresolved_id || '').replace(/^compiler-/, '');
    return value || '未决关系';
};

const compileExtractivePreviewSummary = (draft = {}) => {
    const eventTimeline = [...(draft.event_chains || [])]
        .sort((left, right) => (left.sequence || 0) - (right.sequence || 0))
        .map((item, index) => `${index > 0 ? '随后，' : ''}${item.event}`)
        .join('');
    const archiveBackground = (draft.archive_narratives || [])
        .map((item) => item.summary)
        .filter(Boolean)
        .join(' ');
    const unresolvedCount = (draft.unresolved || []).length;
    const uncertainty = unresolvedCount > 0
        ? `另有 ${unresolvedCount} 项身份、概念或因果关系保持未决，没有被自动补全。`
        : '';
    return [
        eventTimeline && `事件脉络\n${eventTimeline}`,
        archiveBackground && `档案背景\n${archiveBackground}`,
        uncertainty && `未决问题\n${uncertainty}`,
    ].filter(Boolean).join('\n\n');
};

const routeBySourceId = (draft = {}) => {
    const routes = new Map();
    const apply = (items, route) => items.forEach((item) => {
        (item.source_item_ids || []).forEach((sourceId) => {
            if (!routes.has(sourceId)) routes.set(sourceId, route);
        });
    });
    apply(draft.event_chains || [], 'narrative');
    apply(draft.reference_assets || [], 'reference_asset');
    apply(draft.unresolved || [], 'unresolved');
    apply(draft.archive_narratives || [], 'no_context');
    return routes;
};

export const contextResearchPreviewToArchiveTree = (fixture = {}) => {
    const draft = fixture.draft || {};
    const project = fixture.project || {};
    const release = fixture.release || {};
    const routes = routeBySourceId(draft);
    const sourceItems = fixture.source_items || [];
    const sourceById = new Map(sourceItems.map((item) => [item.source_item_id, item]));
    const eventSteps = draft.event_chains || [];
    const chainCounts = eventSteps.reduce((counts, item) => ({
        ...counts,
        [item.chain_id]: (counts[item.chain_id] || 0) + 1,
    }), {});
    const fragmentId = (item) => `fragment-${item.chain_id}${
        chainCounts[item.chain_id] > 1 ? `-${item.sequence}` : ''
    }`;
    const eventFragments = eventSteps.map((item) => ({
        fragment_id: fragmentId(item),
        label: item.event,
        summary: item.event,
        unit_ids: item.source_item_ids || [],
        source_refs: sourceRefs(item),
        route: 'narrative',
        metadata: {
            finding_type: 'event_chain',
            sequence: item.sequence,
            local_unit_ids: item.local_unit_ids || [],
            archive_context_ids: item.archive_context_ids || [],
            entity_ids: item.entity_ids || [],
        },
    }));
    const eventGroups = [...new Set(eventSteps.map((item) => item.chain_id))].map((chainId) => {
        const steps = eventSteps
            .filter((item) => item.chain_id === chainId)
            .sort((left, right) => (left.sequence || 0) - (right.sequence || 0));
        return {
            group_id: `group-${chainId}`,
            story_id: 'story-concrete-events',
            label: steps[0]?.event || chainId,
            summary: steps.map((item) => item.event).join(' '),
            fragment_ids: steps.map(fragmentId),
        };
    });
    const archiveNarratives = (draft.archive_narratives || []).map((item) => ({
        fragment_id: `fragment-${item.narrative_id}`,
        label: archiveLabel(item),
        summary: item.summary,
        unit_ids: item.source_item_ids || [],
        source_refs: sourceRefs(item),
        route: 'no_context',
        metadata: {
            finding_type: 'archive_narrative',
            delivery_target: false,
        },
    }));
    const referenceAssets = (draft.reference_assets || []).map((item, index) => ({
        asset_id: item.asset_id,
        label: item.name,
        summary: item.description || '',
        tier: index === 0 ? 'A' : 'B',
        unit_ids: item.source_item_ids || [],
        source_refs: sourceRefs(item),
        metadata: {
            finding_type: 'reference_asset',
            receives_event_context: false,
        },
    }));
    const entities = (draft.entities || []).map((item) => ({
        candidate_id: item.entity_id,
        candidate_kind: 'entity',
        canonical_display_name: item.name,
        tier: item.frequency_grade
            || (item.importance === 'primary' ? 'A' : item.importance === 'background' ? 'C' : 'B'),
        mention_count: Number.isFinite(Number(item.mention_count))
            ? Number(item.mention_count)
            : unique(item.source_item_ids || []).length,
        local_unit_coverage: Number.isFinite(Number(item.local_unit_coverage))
            ? Number(item.local_unit_coverage)
            : unique(item.local_unit_ids || []).length || unique(item.source_item_ids || []).length,
        summary: item.summary,
        entity_type: item.entity_type,
        aliases: item.aliases || [],
        semantic_importance: item.importance,
        source_files: item.source_files || [],
        file_spread: Number(item.file_spread) || 0,
        event_chain_ids: item.event_chain_ids || [],
        event_participation_count: Number(item.event_participation_count) || 0,
    }));
    const entityEvidence = (draft.entities || []).flatMap((entity) => (
        (entity.evidence || []).flatMap((reference, evidenceIndex) => (
            (reference.source_item_ids || []).map((sourceId) => {
                const source = sourceById.get(sourceId) || {};
                return {
                    evidence_id: `${entity.entity_id}-${evidenceIndex}-${sourceId}`,
                    entity_id: entity.entity_id,
                    source_ref: `${source.path || ''}::${source.key || sourceId}`,
                    excerpt: reference.snippet || source.text || '',
                };
            })
        ))
    ));
    const unresolved = (draft.unresolved || []).map((item) => ({
        fragment_id: `fragment-${item.unresolved_id}`,
        label: unresolvedLabel(item),
        summary: item.reason,
        unit_ids: item.source_item_ids || [],
        source_refs: sourceRefs(item),
        route: 'unresolved',
        metadata: {
            finding_type: 'unresolved',
            reference_type: item.reference_type,
            relation_source_id: item.source_id,
            relation_target_id: item.target_id,
        },
    }));
    return {
        schema_version: 'context-tree-v2-research-preview-v1',
        tree_id: `tree-${project.project_id || 'context-research-preview'}`,
        release_id: release.release_id,
        project_id: project.project_id,
        project_title: project.name,
        project_summary: compileExtractivePreviewSummary(draft),
        preview_metadata: {
            ...(fixture.provenance || {}),
            read_only: true,
            published: false,
        },
        units: sourceItems.map((item) => ({
            unit_id: item.source_item_id,
            label: item.key || item.source_item_id,
            route: routes.get(item.source_item_id) || 'no_context',
            source_ref: `${item.path || ''}::${item.key || ''}`,
            source_text: item.text || '',
        })),
        stories: [{
            story_id: 'story-concrete-events',
            label: 'Remis 政权重组与反对派失踪',
            group_ids: eventGroups.map((group) => group.group_id),
        }],
        groups: eventGroups,
        fragments: eventFragments,
        archive_narratives: archiveNarratives,
        reference_assets: referenceAssets,
        unresolved_fragments: unresolved,
        candidates: entities,
        entity_evidence: entityEvidence,
        compiler_diagnostics: draft.diagnostics?.compiler || {},
    };
};

export default contextResearchPreviewToArchiveTree;

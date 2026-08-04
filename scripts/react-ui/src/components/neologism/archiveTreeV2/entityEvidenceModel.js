const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

const asList = (value) => {
    if (Array.isArray(value)) return value;
    if (!isRecord(value)) return [];
    return Object.entries(value).map(([key, item]) => (
        isRecord(item) ? { ...item, id: item.id ?? key } : { id: key, value: item }
    ));
};

const textValue = (value) => {
    if (value === null || value === undefined || typeof value === 'object') return '';
    const text = String(value).trim();
    return text;
};

const firstText = (containers, keys) => {
    for (const container of containers) {
        if (!isRecord(container)) continue;
        for (const key of keys) {
            const value = textValue(container[key]);
            if (value) return value;
        }
    }
    return '';
};

const firstId = (value, keys = []) => {
    if (value === null || value === undefined) return '';
    if (typeof value !== 'object') return textValue(value);
    for (const key of keys) {
        const id = textValue(value[key]);
        if (id) return id;
    }
    return '';
};

const unique = (values) => [...new Set(values.filter(Boolean).map((value) => String(value)))];

const idKeys = [
    'evidence_id', 'evidenceId', 'fragment_id', 'fragmentId',
    'local_fragment_id', 'localFragmentId', 'local_unit_id', 'localUnitId',
    'chunk_id', 'chunkId', 'unit_id', 'unitId',
    'source_item_id', 'sourceItemId', 'source_id', 'sourceId', 'id', 'key',
];

const segmentIdKeys = [
    'digest_segment_id', 'digestSegmentId', 'segment_id', 'segmentId', 'id', 'key',
];

const descriptionKeys = [
    'local_description', 'localDescription', 'short_summary', 'shortSummary',
    'description', 'snippet', 'summary', 'source_text', 'sourceText', 'content', 'text',
];

const sourceRefKeys = ['source_ref', 'sourceRef', 'path', 'file', 'uri'];

const evidenceKeys = [
    'evidence', 'evidence_items', 'evidenceItems', 'all_evidence', 'allEvidence',
    'full_evidence', 'fullEvidence', 'fragment_evidence', 'fragmentEvidence',
    'all_fragment_evidence', 'allFragmentEvidence', 'local_fragment_evidence',
    'localFragmentEvidence', 'evidence_fragments', 'evidenceFragments',
    'evidence_units', 'evidenceUnits', 'fragments', 'local_fragments', 'localFragments',
    'full_fragment_evidence', 'fullFragmentEvidence', 'chunk_evidence', 'chunkEvidence',
    'all_chunk_evidence', 'allChunkEvidence', 'source_item_evidence', 'sourceItemEvidence',
    'source_items', 'sourceItems',
];

const fullEvidenceKeys = new Set([
    'evidence', 'evidence_items', 'evidenceItems', 'all_evidence', 'allEvidence',
    'full_evidence', 'fullEvidence', 'fragment_evidence', 'fragmentEvidence',
    'all_fragment_evidence', 'allFragmentEvidence', 'local_fragment_evidence',
    'localFragmentEvidence', 'evidence_fragments', 'evidenceFragments',
    'evidence_units', 'evidenceUnits', 'fragments', 'local_fragments', 'localFragments',
    'full_fragment_evidence', 'fullFragmentEvidence', 'chunk_evidence', 'chunkEvidence',
    'all_chunk_evidence', 'allChunkEvidence', 'source_item_evidence', 'sourceItemEvidence',
    'source_items', 'sourceItems',
]);

const evidenceIdKeys = [
    'all_evidence_ids', 'allEvidenceIds', 'full_evidence_ids', 'fullEvidenceIds',
    'evidence_ids', 'evidenceIds', 'fragment_ids', 'fragmentIds',
    'local_fragment_ids', 'localFragmentIds', 'unit_ids', 'unitIds',
    'source_item_ids', 'sourceItemIds', 'evidence_source_item_ids', 'evidenceSourceItemIds',
];

const digestOnlyIdKeys = ['summary_evidence_source_item_ids', 'summaryEvidenceSourceItemIds'];

const segmentKeys = [
    'digest_segments', 'digestSegments', 'partial_digests', 'partialDigests',
    'partial_segments', 'partialSegments', 'segments', 'partial_digest', 'partialDigest',
    'digest_segment', 'digestSegment',
];

const singularSegmentKeys = new Set([
    'partial_digest', 'partialDigest', 'digest_segment', 'digestSegment',
]);

const segmentTextKeys = [
    'partial_digest', 'partialDigest', 'partial_digest_text', 'partialDigestText',
    'digest', 'summary', 'text', 'content', 'description', 'value',
];

const segmentEvidenceKeys = [
    'evidence', 'evidence_items', 'evidenceItems', 'evidence_ids', 'evidenceIds',
    'fragment_ids', 'fragmentIds', 'local_fragment_ids', 'localFragmentIds',
    'unit_ids', 'unitIds', 'source_item_ids', 'sourceItemIds',
    'evidence_source_item_ids', 'evidenceSourceItemIds',
];

const nestedKeys = [
    'digest', 'digest_data', 'digestData', 'entity_evidence', 'entityEvidence',
    'evidence_details', 'evidenceDetails', 'summary_details', 'summaryDetails',
    'synthesis',
];

const globalEvidenceKeys = [
    'source_items', 'sourceItems', 'local_units', 'localUnits',
    'local_fragments', 'localFragments', 'fragments', 'evidence', 'all_evidence',
    'allEvidence', 'fragment_evidence', 'fragmentEvidence',
];

const aggregateIdFor = (entry) => firstId(entry, ['aggregate_id', 'aggregateId', 'entity_id', 'entityId']);

const containersFor = (entry, preview) => {
    const payload = isRecord(entry?.payload) ? entry.payload : {};
    const containers = [entry, payload];
    [...containers].forEach((container) => {
        nestedKeys.forEach((key) => {
            if (isRecord(container?.[key])) containers.push(container[key]);
        });
    });

    const aggregateId = aggregateIdFor(entry);
    const globalMaps = [
        preview?.entity_evidence,
        preview?.entityEvidence,
        preview?.digest_by_aggregate,
        preview?.digestByAggregate,
        preview?.evidence_by_aggregate,
        preview?.evidenceByAggregate,
    ];
    globalMaps.forEach((map) => {
        if (!isRecord(map) || !aggregateId || !isRecord(map[aggregateId])) return;
        containers.push(map[aggregateId]);
    });
    return containers;
};

const sourceRowsFor = (preview) => {
    const sources = [];
    const containers = [preview, preview?.data, preview?.context];
    containers.forEach((container) => {
        if (!isRecord(container)) return;
        globalEvidenceKeys.forEach((key) => sources.push(...asList(container[key])));
    });
    return sources;
};

const sourceIndexFor = (preview) => {
    const index = new Map();
    sourceRowsFor(preview).forEach((source) => {
        const ids = unique(idKeys.map((key) => firstId(source, [key])));
        ids.forEach((id) => {
            if (!index.has(id)) index.set(id, source);
        });
    });
    return index;
};

const idsFrom = (value) => asList(value).map((item) => firstId(item, idKeys) || firstId(item, ['value']));

const idsFromContainers = (containers, keys) => unique(
    containers.flatMap((container) => keys.flatMap((key) => idsFrom(container?.[key]))),
);

const hasNonEmptyField = (containers, keys) => containers.some((container) => (
    isRecord(container) && keys.some((key) => {
        const value = container[key];
        return Array.isArray(value) ? value.length > 0 : isRecord(value) && Object.keys(value).length > 0;
    })
));

const normalizeTier = (value) => {
    const tier = textValue(value).toLowerCase();
    if (tier === 'a' || tier === 'core') return 'A';
    if (tier === 'b' || tier === 'secondary') return 'B';
    if (tier === 'c' || tier === 'incidental') return 'C';
    return tier ? tier.toUpperCase() : '—';
};

const isDigestTier = (tier) => tier === 'A' || tier === 'B';

const segmentRefs = (raw) => segmentEvidenceKeys.flatMap((key) => idsFrom(raw?.[key]));

const normalizeSegment = (raw, index, kind = 'digest') => {
    const id = firstId(raw, segmentIdKeys) || `${kind}-segment-${index + 1}`;
    const text = typeof raw === 'string' ? raw : firstText([raw], segmentTextKeys);
    const evidenceItems = segmentEvidenceKeys.flatMap((key) => asList(raw?.[key]))
        .filter((item) => isRecord(item));
    return {
        id,
        text,
        evidenceIds: unique(segmentRefs(raw)),
        evidenceItems,
    };
};

const collectSegments = (containers) => {
    const segments = [];
    containers.forEach((container) => {
        if (!isRecord(container)) return;
        segmentKeys.forEach((key) => {
            const values = singularSegmentKeys.has(key)
                ? (container[key] === undefined ? [] : [container[key]])
                : asList(container[key]);
            values.forEach((raw, index) => {
                segments.push(normalizeSegment(raw, segments.length + index, key.includes('partial') ? 'partial' : 'digest'));
            });
        });
    });
    const seen = new Set();
    return segments.filter((segment) => {
        const key = `${segment.id}\u0000${segment.text}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
};

const sourceFor = (raw, sourceIndex) => {
    const ids = unique(idKeys.map((key) => firstId(raw, [key])));
    return ids.map((id) => sourceIndex.get(id)).find(Boolean);
};

const mergeText = (left, right) => left || right || '';

const evidenceFromRaw = (raw, inheritedSegmentIds, sourceIndex, index) => {
    const source = sourceFor(raw, sourceIndex);
    const sourceContainers = [raw, source];
    const id = firstId(raw, idKeys) || firstId(source, idKeys) || `evidence-${index + 1}`;
    const fragmentId = firstId(raw, ['fragment_id', 'fragmentId', 'local_fragment_id', 'localFragmentId']);
    const unitId = firstId(raw, ['unit_id', 'unitId']);
    const sourceItemId = firstId(raw, ['source_item_id', 'sourceItemId', 'source_id', 'sourceId'])
        || firstId(source, ['source_item_id', 'sourceItemId', 'source_id', 'sourceId']);
    const description = firstText(sourceContainers, descriptionKeys);
    const sourceRef = firstText(sourceContainers, sourceRefKeys);
    const segmentIds = unique([
        ...inheritedSegmentIds,
        ...idsFrom(raw?.digest_segment_ids || raw?.digestSegmentIds),
        ...idsFrom(raw?.segment_ids || raw?.segmentIds),
        firstId(raw, ['digest_segment_id', 'digestSegmentId']),
        firstId(raw, ['segment_id', 'segmentId']),
    ]);
    return {
        id,
        fragmentId,
        unitId,
        sourceItemId,
        sourceRef,
        localDescription: description,
        digestSegmentIds: segmentIds,
    };
};

const mergeEvidence = (existing, incoming) => ({
    ...existing,
    ...incoming,
    fragmentId: mergeText(existing.fragmentId, incoming.fragmentId),
    unitId: mergeText(existing.unitId, incoming.unitId),
    sourceItemId: mergeText(existing.sourceItemId, incoming.sourceItemId),
    sourceRef: mergeText(existing.sourceRef, incoming.sourceRef),
    localDescription: mergeText(existing.localDescription, incoming.localDescription),
    digestSegmentIds: unique([
        ...(existing.digestSegmentIds || []),
        ...(incoming.digestSegmentIds || []),
    ]),
});

const addEvidence = (map, order, raw, segmentIds, sourceIndex) => {
    const evidence = evidenceFromRaw(raw, segmentIds, sourceIndex, order.length);
    if (!map.has(evidence.id)) order.push(evidence.id);
    map.set(evidence.id, map.has(evidence.id) ? mergeEvidence(map.get(evidence.id), evidence) : evidence);
};

const evidenceRowsFromContainers = (containers, sourceIndex, segmentMap, segments = []) => {
    const map = new Map();
    const order = [];
    containers.forEach((container) => {
        if (!isRecord(container)) return;
        evidenceKeys.forEach((key) => {
            asList(container[key]).forEach((raw) => addEvidence(map, order, raw, [], sourceIndex));
        });
    });
    segments.forEach((segment) => {
        segment.evidenceItems.forEach((raw) => addEvidence(map, order, raw, [segment.id], sourceIndex));
        segment.evidenceIds.forEach((evidenceId) => addEvidence(map, order, evidenceId, [segment.id], sourceIndex));
    });
    segmentMap.forEach((segmentIds, evidenceId) => {
        const source = sourceIndex.get(evidenceId);
        addEvidence(map, order, source || evidenceId, segmentIds, sourceIndex);
    });
    return { map, order };
};

const referenceIdsFor = (containers, includeDigestOnly = false) => idsFromContainers(
    containers,
    includeDigestOnly ? [...evidenceIdKeys, ...digestOnlyIdKeys] : evidenceIdKeys,
);

const fillReferencedEvidence = (map, order, ids, sourceIndex) => {
    ids.forEach((id) => addEvidence(map, order, sourceIndex.get(id) || id, [], sourceIndex));
};

const mechanicalDescriptionFor = (containers, evidence) => {
    const provided = firstText(containers, [
        'mechanical_local_description', 'mechanicalLocalDescription',
        'mechanical_description', 'mechanicalDescription',
        'local_description_concat', 'localDescriptionConcat',
        'concatenated_local_descriptions', 'concatenatedLocalDescriptions',
        'mechanically_joined_description', 'mechanicallyJoinedDescription',
    ]);
    if (provided) return { text: provided, source: 'provided' };
    const descriptions = evidence.map((item) => item.localDescription).filter(Boolean);
    return descriptions.length > 0
        ? { text: descriptions.join('\n\n'), source: 'joined' }
        : { text: '', source: 'missing' };
};

const finalDigestFor = (entry, containers, isSummaryTier) => {
    if (!isSummaryTier) return '';
    return firstText([entry, ...containers], [
        'final_digest', 'finalDigest', 'final_summary', 'finalSummary', 'summary', 'digest',
    ]);
};

const normalizeEvidence = (evidence, segmentMap) => evidence.map((item) => {
    const segmentIds = unique([
        ...(item.digestSegmentIds || []),
        ...(segmentMap.get(item.id) || []),
        ...(item.fragmentId ? segmentMap.get(item.fragmentId) || [] : []),
        ...(item.unitId ? segmentMap.get(item.unitId) || [] : []),
        ...(item.sourceItemId ? segmentMap.get(item.sourceItemId) || [] : []),
    ]);
    return {
        ...item,
        digestSegmentIds: segmentIds,
        digestSegmentId: segmentIds[0] || '',
        displayId: item.fragmentId || item.unitId || item.sourceItemId || item.id,
    };
});

export const normalizeEntityEvidence = (entry, preview = {}) => {
    const containers = containersFor(entry, preview);
    const sourceIndex = sourceIndexFor(preview);
    const segments = collectSegments(containers);
    const segmentMap = new Map();
    segments.forEach((segment) => {
        segment.evidenceIds.forEach((id) => {
            segmentMap.set(id, unique([...(segmentMap.get(id) || []), segment.id]));
        });
    });
    const collected = evidenceRowsFromContainers(containers, sourceIndex, segmentMap, segments);
    const explicitFullIds = referenceIdsFor(containers);
    fillReferencedEvidence(collected.map, collected.order, explicitFullIds, sourceIndex);
    const digestOnlyIds = referenceIdsFor(containers, true).filter((id) => !explicitFullIds.includes(id));
    fillReferencedEvidence(collected.map, collected.order, digestOnlyIds, sourceIndex);
    const evidence = normalizeEvidence(collected.order.map((id) => collected.map.get(id)), segmentMap);
    const tier = normalizeTier(firstText(containers, ['tier', 'candidate_tier', 'candidateTier']));
    const summaryTier = tier === '—'
        ? firstText(containers, ['summary_eligible']) === 'true'
        : isDigestTier(tier);
    const mechanical = mechanicalDescriptionFor(containers, evidence);
    const partialDigests = summaryTier ? segments
        .filter((segment) => segment.text)
        .map((segment) => ({
            id: segment.id,
            digestSegmentId: segment.id,
            text: segment.text,
            evidenceIds: segment.evidenceIds,
        })) : [];
    const completeSignal = containers
        .map((container) => container?.evidence_complete ?? container?.evidenceComplete
            ?? container?.full_evidence_available ?? container?.fullEvidenceAvailable)
        .find((value) => typeof value === 'boolean');
    const hasSegmentEvidence = segments.some((segment) => segment.evidenceIds.length > 0 || segment.evidenceItems.length > 0);
    const hasFullEvidenceField = hasNonEmptyField(containers, [...fullEvidenceKeys, 'all_evidence_ids', 'allEvidenceIds', 'full_evidence_ids', 'fullEvidenceIds'])
        || hasSegmentEvidence;
    return {
        aggregateId: aggregateIdFor(entry),
        label: firstText([entry], ['label', 'aggregate_key', 'aggregateKey']),
        tier,
        isSummaryTier: summaryTier,
        finalDigest: finalDigestFor(entry, containers, summaryTier),
        mechanicalLocalDescription: mechanical.text,
        mechanicalDescriptionSource: mechanical.source,
        partialDigests,
        digestSegments: segments,
        evidence,
        evidenceIsComplete: completeSignal ?? hasFullEvidenceField,
        evidenceCount: evidence.length,
    };
};

export const getEntityEvidenceEntries = (preview) => (preview?.entries || [])
    .filter((entry) => entry?.aggregate_type === 'entity')
    .map((entry) => normalizeEntityEvidence(entry, preview));

export const getEntityEvidenceForEntry = (preview, aggregateId) => getEntityEvidenceEntries(preview)
    .find((entry) => entry.aggregateId === String(aggregateId)) || null;

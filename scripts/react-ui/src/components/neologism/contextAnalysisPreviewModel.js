const numberValue = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

export const entityCoverage = (entry) => Math.max(
    numberValue(entry?.payload?.local_unit_coverage),
    numberValue(entry?.payload?.source_item_coverage),
);

const matchesSearch = (entry, query) => {
    if (!query) return true;
    const payload = entry.payload || {};
    return [
        entry.label,
        entry.aggregate_key,
        entry.summary,
        ...(payload.aliases || []),
        payload.event,
        payload.consequence,
        ...(payload.participants || []),
    ].some((value) => String(value || '').toLocaleLowerCase().includes(query));
};

const matchesSummary = (entry, filter) => (
    filter === 'all'
    || (filter === 'with_summary' && Boolean(entry.summary))
    || (filter === 'without_summary' && !entry.summary)
);

const matchesPolicy = (entry, filter) => {
    if (filter === 'all') return true;
    if (filter === 'summary_eligible') return entry.payload?.summary_eligible === true;
    if (filter === 'glossary_eligible') return entry.payload?.glossary_eligible === true;
    if (filter === 'audit_only') return entry.payload?.audit_only === true;
    return true;
};

export const filterAnalysisPreviewEntries = (
    entries,
    {
        section = 'entity',
        search = '',
        kind = 'all',
        tier = 'all',
        summary = 'all',
        policy = 'all',
    } = {},
) => {
    const query = search.trim().toLocaleLowerCase();
    return (entries || [])
        .filter((entry) => entry.aggregate_type === section)
        .filter((entry) => matchesSearch(entry, query))
        .filter((entry) => (
            section !== 'entity' || kind === 'all' || entry.payload?.candidate_kind === kind
        ))
        .filter((entry) => (
            section !== 'entity' || tier === 'all' || entry.payload?.tier === tier
        ))
        .filter((entry) => matchesSummary(entry, summary))
        .filter((entry) => section !== 'entity' || matchesPolicy(entry, policy))
        .sort((left, right) => (
            section === 'entity'
                ? ({ core: 0, secondary: 1, incidental: 2 }[left.payload?.tier] ?? 3)
                    - ({ core: 0, secondary: 1, incidental: 2 }[right.payload?.tier] ?? 3)
                    || left.label.localeCompare(right.label)
                : numberValue(right.payload?.delivery_coverage?.local_unit_coverage)
                    - numberValue(left.payload?.delivery_coverage?.local_unit_coverage)
                    || left.label.localeCompare(right.label)
        ));
};

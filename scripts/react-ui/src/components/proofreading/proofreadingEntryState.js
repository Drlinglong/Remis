export const isProofreadingRowChanged = row => (
    row.editable && row.final_value !== row.baseline_value
);

const BRACKET_TOKEN_PATTERN = new RegExp('\\[[^\\[\\]\\r\\n]+\\]', 'g');

export const extractBracketTokens = value => (
    String(value || '').match(BRACKET_TOKEN_PATTERN) || []
);

const countTokens = tokens => tokens.reduce((counts, token) => {
    counts.set(token, (counts.get(token) || 0) + 1);
    return counts;
}, new Map());

export const getBracketVariableWarnings = rows => rows
    .filter(row => row.row_type === 'translation' && isProofreadingRowChanged(row))
    .map(row => {
        const baselineCounts = countTokens(extractBracketTokens(row.baseline_value));
        const currentCounts = countTokens(extractBracketTokens(row.final_value));
        const tokens = new Set([...baselineCounts.keys(), ...currentCounts.keys()]);
        const changes = [...tokens]
            .map(token => ({
                token,
                before: baselineCounts.get(token) || 0,
                after: currentCounts.get(token) || 0,
            }))
            .filter(change => change.before !== change.after);

        return changes.length ? { key: row.key, entry_id: row.entry_id, changes } : null;
    })
    .filter(Boolean);

export const getProofreadingDraftPatches = rows => rows
    .filter(isProofreadingRowChanged)
    .map(row => ({
        entry_id: row.entry_id,
        key: row.key || null,
        row_type: row.row_type,
        final_value: row.final_value || '',
    }));

export const applyProofreadingDraftPatches = (rows, patches) => {
    const patchesByEntryId = new Map((patches || []).map(patch => [patch.entry_id, patch]));
    const translationPatchesByKey = new Map(
        (patches || [])
            .filter(patch => patch.row_type === 'translation' && patch.key)
            .map(patch => [patch.key, patch])
    );

    return rows.map(row => {
        const patch = patchesByEntryId.get(row.entry_id)
            || (row.row_type === 'translation' ? translationPatchesByKey.get(row.key) : null);
        return patch ? { ...row, final_value: patch.final_value } : row;
    });
};

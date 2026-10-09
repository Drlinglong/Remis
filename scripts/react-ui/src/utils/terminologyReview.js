export const reviewStates = ['candidate', 'reviewed', 'pending', 'approved', 'rejected'];
export const confidenceBands = ['high', 'medium', 'low', 'unrated'];

export function parseReviewMetadata(raw) {
    try {
        const metadata = typeof raw === 'string' ? JSON.parse(raw || '{}') : raw;
        return metadata && typeof metadata === 'object' && !Array.isArray(metadata) ? metadata : {};
    } catch {
        return null;
    }
}

export function reviewBasis(values, term) {
    return { source: values.source, translation: values.translation,
        sense: term.sense || '', context_keys: term.context_keys || [] };
}

export function parseTermVariants(variants = []) {
    return variants.reduce((result, item) => {
        if (item.lang && item.value) {
            result[item.lang] = item.value.split(',').map(value => value.trim()).filter(Boolean);
        }
        return result;
    }, {});
}

function currentEnglishAliases(values, term) {
    return parseTermVariants(values.variants).en ?? term.aliases ?? [];
}

export function effectiveReviewState(term, values) {
    if (!term) return null;
    const basis = term.review_basis;
    const current = reviewBasis(values, term);
    if (['reviewed', 'approved'].includes(term.review_state)
        && (!basis || basis.source !== current.source || basis.translation !== current.translation
            || basis.sense !== current.sense
            || JSON.stringify(basis.context_keys) !== JSON.stringify(current.context_keys)
            || (term.alias_review_basis
                && JSON.stringify(term.alias_review_basis) !== JSON.stringify(currentEnglishAliases(values, term))))) return 'candidate';
    return term.review_state || 'candidate';
}

export function updateReviewMetadata(raw, patch, values) {
    const metadata = parseReviewMetadata(raw);
    if (!metadata?.terminology) return raw;
    const terminology = { ...metadata.terminology, ...patch };
    if (['reviewed', 'approved'].includes(patch.review_state)) {
        terminology.review_basis = reviewBasis(values, terminology);
        terminology.alias_review_basis = currentEnglishAliases(values, terminology);
    }
    terminology.review_state = effectiveReviewState(terminology, values);
    return JSON.stringify({ ...metadata, terminology }, null, 2);
}

export function prepareReviewMetadata(raw, values, locale) {
    const metadata = parseReviewMetadata(raw);
    if (!metadata) return {};
    const term = metadata.terminology;
    if (!term || term.locale !== locale) return metadata;
    return { ...metadata, terminology: { ...term, review_state: effectiveReviewState(term, values) } };
}

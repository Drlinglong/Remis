export const settleWithConcurrency = async (items, operation, concurrency = 4) => {
    if (items.length === 0) return [];

    const results = new Array(items.length);
    let nextIndex = 0;
    const worker = async () => {
        while (nextIndex < items.length) {
            const index = nextIndex;
            nextIndex += 1;
            try {
                results[index] = {
                    status: 'fulfilled',
                    value: await operation(items[index], index),
                };
            } catch (reason) {
                results[index] = { status: 'rejected', reason };
            }
        }
    };

    await Promise.all(Array.from(
        { length: Math.min(concurrency, items.length) },
        () => worker(),
    ));
    return results;
};

export const partitionSettledCandidateIds = (items, results) => {
    const succeededIds = [];
    const failedIds = [];

    results.forEach((result, index) => {
        const id = items[index]?.id ?? items[index];
        (result.status === 'fulfilled' ? succeededIds : failedIds).push(id);
    });

    return { succeededIds, failedIds };
};

export const candidateDraftKey = (projectId, candidateId) => (
    `${projectId || ''}:${candidateId}`
);

export const candidateEvidence = (candidate) => {
    if (!candidate) return [];
    if ((candidate.context_evidence || []).length > 0) return candidate.context_evidence;
    return (candidate.context_snippets || []).map((snippet) => ({
        snippet,
        source_file: null,
        legacy: true,
    }));
};

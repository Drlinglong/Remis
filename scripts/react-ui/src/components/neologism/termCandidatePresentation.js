const tierOrder = { A: 0, core: 0, B: 1, secondary: 1, C: 2, incidental: 2 };

export const candidateTierFromFrequency = (candidate) => {
    const rawFrequency = candidate?.frequency;
    if (rawFrequency !== undefined && rawFrequency !== null && rawFrequency !== '') {
        const frequency = Number(rawFrequency);
        if (Number.isFinite(frequency)) {
            if (frequency >= 3) return 'A';
            if (frequency === 2) return 'B';
            return 'C';
        }
    }

    return ['A', 'B', 'C'].includes(candidate?.tier) ? candidate.tier : 'C';
};

export const sortTermCandidates = (items) => items.map((candidate) => ({
    ...candidate,
    tier: candidateTierFromFrequency(candidate),
})).sort((left, right) => {
    const grade = (tierOrder[left.tier] ?? 3) - (tierOrder[right.tier] ?? 3);
    return grade || String(left.original || '').localeCompare(String(right.original || ''), undefined, {
        sensitivity: 'base',
    });
});

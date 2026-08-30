const tierOrder = { A: 0, core: 0, B: 1, secondary: 1, C: 2, incidental: 2 };

export const sortTermCandidates = (items) => [...items].sort((left, right) => {
    const grade = (tierOrder[left.tier] ?? 3) - (tierOrder[right.tier] ?? 3);
    return grade || String(left.original || '').localeCompare(String(right.original || ''), undefined, {
        sensitivity: 'base',
    });
});

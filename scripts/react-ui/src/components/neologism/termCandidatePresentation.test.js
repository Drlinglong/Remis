import { describe, expect, it } from 'vitest';

import { sortTermCandidates } from './termCandidatePresentation';

describe('sortTermCandidates', () => {
    it('sorts A, B, C and then alphabetically within each grade', () => {
        const result = sortTermCandidates([
            { original: 'Zulu', tier: 'B' },
            { original: 'Beta', tier: 'A' },
            { original: 'Alpha', tier: 'A' },
            { original: 'Archive', tier: 'C' },
        ]);
        expect(result.map((item) => item.original)).toEqual(['Alpha', 'Beta', 'Zulu', 'Archive']);
    });
});

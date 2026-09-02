import { describe, expect, it } from 'vitest';

import { candidateTierFromFrequency, sortTermCandidates } from './termCandidatePresentation';

describe('candidate importance tiers', () => {
    it('derives A, B, and C from the persisted frequency contract', () => {
        expect(candidateTierFromFrequency({ frequency: 7, confidence: 0.1 })).toBe('A');
        expect(candidateTierFromFrequency({ frequency: 3, confidence: 0.1 })).toBe('A');
        expect(candidateTierFromFrequency({ frequency: 2, confidence: 0.99 })).toBe('B');
        expect(candidateTierFromFrequency({ frequency: 1, confidence: 0.99 })).toBe('C');
        expect(candidateTierFromFrequency({ frequency: 0, confidence: 0.99 })).toBe('C');
    });

    it('sorts candidates using the derived frequency tier instead of model confidence', () => {
        const result = sortTermCandidates([
            { original: 'Low', frequency: 1, confidence: 1 },
            { original: 'High', frequency: 3, confidence: 0 },
            { original: 'Medium', frequency: 2, confidence: 0.5 },
        ]);
        expect(result.map(({ original, tier }) => [original, tier])).toEqual([
            ['High', 'A'],
            ['Medium', 'B'],
            ['Low', 'C'],
        ]);
    });
});

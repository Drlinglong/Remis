import { describe, expect, it, vi } from 'vitest';

import {
    candidateDraftKey,
    candidateEvidence,
    partitionSettledCandidateIds,
    settleWithConcurrency,
} from './judgmentCourtWorkflow';

describe('judgmentCourtWorkflow', () => {
    it('keeps project-scoped drafts separate', () => {
        expect(candidateDraftKey('project-a', 7)).toBe('project-a:7');
        expect(candidateDraftKey('project-b', 7)).toBe('project-b:7');
    });

    it('normalizes legacy snippets without inventing source evidence', () => {
        expect(candidateEvidence({ context_snippets: ['A relay activates.'] })).toEqual([{
            snippet: 'A relay activates.',
            source_file: null,
            legacy: true,
        }]);
    });

    it('never runs more than four batch requests concurrently', async () => {
        let active = 0;
        let peak = 0;
        const releases = [];
        const operation = vi.fn(async (item) => {
            active += 1;
            peak = Math.max(peak, active);
            await new Promise((resolve) => releases.push(resolve));
            active -= 1;
            return item;
        });

        const pending = settleWithConcurrency([1, 2, 3, 4, 5, 6], operation, 4);
        await vi.waitFor(() => expect(operation).toHaveBeenCalledTimes(4));
        releases.splice(0).forEach((release) => release());
        await vi.waitFor(() => expect(operation).toHaveBeenCalledTimes(6));
        releases.splice(0).forEach((release) => release());
        await pending;

        expect(peak).toBe(4);
    });

    it('partitions successes and failures without dropping failed selections', () => {
        expect(partitionSettledCandidateIds(
            [{ id: 1 }, { id: 2 }, { id: 3 }],
            [
                { status: 'fulfilled', value: {} },
                { status: 'rejected', reason: new Error('failed') },
                { status: 'fulfilled', value: {} },
            ],
        )).toEqual({ succeededIds: [1, 3], failedIds: [2] });
    });
});

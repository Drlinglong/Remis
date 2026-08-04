import { describe, expect, it } from 'vitest';

import {
    getEntityEvidenceEntries,
    normalizeEntityEvidence,
} from './entityEvidenceModel';

const preview = {
    source_items: [
        {
            source_item_id: 'source-1',
            source_ref: 'events/intro.txt::1',
            local_description: 'The order enters the chamber.',
        },
        {
            source_item_id: 'source-2',
            source_ref: 'events/finale.txt::2',
            local_description: 'The entity opens the gate.',
        },
    ],
    entries: [{
        aggregate_id: 'entity-1',
        aggregate_type: 'entity',
        label: 'The entity',
        summary: 'The final LLM digest.',
        payload: {
            tier: 'core',
            evidence_complete: true,
            evidence: [
                {
                    fragment_id: 'fragment-1',
                    unit_id: 'unit-1',
                    source_item_id: 'source-1',
                    local_description: 'The order enters the chamber.',
                    digest_segment_id: 'segment-1',
                },
                {
                    fragment_id: 'fragment-2',
                    unit_id: 'unit-2',
                    source_item_id: 'source-2',
                    local_description: 'The entity opens the gate.',
                    digest_segment_id: 'segment-2',
                },
            ],
            mechanical_local_description: 'The order enters the chamber.\n\nThe entity opens the gate.',
            partial_digests: [
                { digest_segment_id: 'segment-1', partial_digest: 'Arrival.' },
                { digest_segment_id: 'segment-2', partial_digest: 'Consequence.' },
            ],
        },
    }],
};

describe('entity evidence model', () => {
    it('keeps all fragment evidence and exposes segment, mechanical, partial, and final digests', () => {
        const details = normalizeEntityEvidence(preview.entries[0], preview);

        expect(details.evidence.map((item) => item.fragmentId)).toEqual(['fragment-1', 'fragment-2']);
        expect(details.evidence.map((item) => item.digestSegmentId)).toEqual(['segment-1', 'segment-2']);
        expect(details.mechanicalLocalDescription).toBe('The order enters the chamber.\n\nThe entity opens the gate.');
        expect(details.partialDigests.map((item) => item.digestSegmentId)).toEqual(['segment-1', 'segment-2']);
        expect(details.finalDigest).toBe('The final LLM digest.');
        expect(details.evidenceIsComplete).toBe(true);
    });

    it('does not invent a C-level final digest and still returns the entity detail shape', () => {
        const entry = {
            ...preview.entries[0],
            aggregate_id: 'entity-c',
            summary: 'Should not be shown as a C digest.',
            payload: { ...preview.entries[0].payload, tier: 'incidental' },
        };

        const details = normalizeEntityEvidence(entry, preview);

        expect(details.isSummaryTier).toBe(false);
        expect(details.finalDigest).toBe('');
        expect(details.evidence).toHaveLength(2);
    });

    it('can derive evidence rows directly from digest segments', () => {
        const entry = {
            aggregate_id: 'entity-segmented',
            aggregate_type: 'entity',
            label: 'Segmented entity',
            payload: {
                tier: 'core',
                digest_segments: [{
                    digest_segment_id: 'segment-embedded',
                    partial_digest: 'Embedded partial.',
                    evidence: [{
                        fragment_id: 'fragment-embedded',
                        local_description: 'Embedded local description.',
                    }],
                }],
            },
        };

        const details = normalizeEntityEvidence(entry);

        expect(details.evidence).toHaveLength(1);
        expect(details.evidence[0]).toMatchObject({
            fragmentId: 'fragment-embedded',
            digestSegmentId: 'segment-embedded',
            localDescription: 'Embedded local description.',
        });
        expect(details.partialDigests[0].text).toBe('Embedded partial.');
        expect(details.evidenceIsComplete).toBe(true);
    });

    it('normalizes only entity entries for preview lists', () => {
        const entries = getEntityEvidenceEntries({
            ...preview,
            entries: [...preview.entries, { aggregate_id: 'event-1', aggregate_type: 'event' }],
        });

        expect(entries).toHaveLength(1);
        expect(entries[0].aggregateId).toBe('entity-1');
    });
});

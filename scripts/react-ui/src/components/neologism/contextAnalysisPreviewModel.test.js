import { describe, expect, it } from 'vitest';

import { filterAnalysisPreviewEntries } from './contextAnalysisPreviewModel';

const entries = [
    {
        aggregate_id: 'entity-core',
        aggregate_type: 'entity',
        label: 'Toxic God',
        summary: 'A recurring godlike entity.',
        payload: {
            aliases: ['The Toxic God'],
            candidate_kind: 'entity',
            tier: 'core',
            local_unit_coverage: 8,
            summary_eligible: true,
        },
    },
    {
        aggregate_id: 'entity-audit',
        aggregate_type: 'entity',
        label: 'advanced field equations',
        summary: null,
        payload: {
            candidate_kind: 'incidental_concept',
            tier: 'incidental',
            local_unit_coverage: 1,
            audit_only: true,
        },
    },
    {
        aggregate_id: 'event-1',
        aggregate_type: 'event',
        label: 'chain_toxic_god',
        summary: 'The order starts its quest.',
        payload: {
            participants: ['Toxic God', 'Order'],
            delivery_coverage: { local_unit_coverage: 12 },
        },
    },
];

describe('context analysis preview model', () => {
    it('filters merged candidates by policy without hiding audit data permanently', () => {
        expect(filterAnalysisPreviewEntries(entries, {
            section: 'entity',
            policy: 'audit_only',
        }).map((entry) => entry.aggregate_id)).toEqual(['entity-audit']);
        expect(filterAnalysisPreviewEntries(entries, {
            section: 'entity',
            search: 'the toxic god',
        }).map((entry) => entry.aggregate_id)).toEqual(['entity-core']);
    });

    it('searches event participants and keeps entity and event views separate', () => {
        expect(filterAnalysisPreviewEntries(entries, {
            section: 'event',
            search: 'order',
            kind: 'incidental_concept',
            tier: 'incidental',
        }).map((entry) => entry.aggregate_id)).toEqual(['event-1']);
    });
});

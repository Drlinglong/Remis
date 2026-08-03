import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it } from 'vitest';

import { getTraceabilityRows } from './modArchiveModel';
import CandidateGovernanceSection from './CandidateGovernanceSection';

const t = (key) => key;

const candidateRows = getTraceabilityRows([
    {
        aggregate: {
            aggregate_key: 'entity:term',
            aggregate_type: 'entity',
            canonical_display_name: 'Admiralty',
            normalized_match_key: 'admiralty',
            aliases: ['Admiralty', 'The Admiralty'],
            candidate_kind: 'glossary_term',
            tier: 'secondary',
            mention_count: 4,
            source_item_coverage: 3,
            local_unit_coverage: 2,
            event_chain_coverage: 1,
            summary_eligible: false,
            glossary_eligible: true,
        },
        contributions: [{ source_item: { source_ref: 'source::term' } }],
    },
    {
        aggregate: {
            aggregate_key: 'entity:concept',
            aggregate_type: 'entity',
            canonical_display_name: 'Background concept',
            normalized_match_key: 'background concept',
            aliases: ['Background concept'],
            candidate_kind: 'incidental_concept',
            tier: 'core',
            audit_only: true,
        },
        contributions: [{ source_item: { source_ref: 'source::concept' } }],
    },
]);

const renderSection = (rows = candidateRows) => render(
    <MantineProvider>
        <CandidateGovernanceSection rows={rows} t={t} />
    </MantineProvider>,
);

describe('CandidateGovernanceSection', () => {
    it('shows the actual candidate kind separately from the secondary tier group', () => {
        renderSection();

        const secondaryCard = screen.getByTestId('mod-archive-candidate-secondary-0');
        expect(secondaryCard).toHaveAttribute(
            'data-candidate-group',
            'secondary',
        );
        expect(screen.getByText('mod_archive.release.candidate_kind.glossary_term')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.candidate_tier.secondary')).toBeInTheDocument();
        expect(screen.getByText('Admiralty, The Admiralty')).toBeInTheDocument();
        expect(secondaryCard).toHaveTextContent('mod_archive.release.candidate_coverage.source_item_coverage');
        expect(secondaryCard).toHaveTextContent('mod_archive.release.candidate_coverage.local_unit_coverage');
        expect(secondaryCard).toHaveTextContent('mod_archive.release.candidate_coverage.event_chain_coverage');
    });

    it('keeps incidental and audit-only candidates in a collapsed low-priority section', () => {
        renderSection();

        const auditSection = screen.getByTestId('mod-archive-candidate-audit');
        expect(auditSection).not.toHaveAttribute('open');
        expect(screen.getByTestId('mod-archive-candidate-incidental-0')).toHaveAttribute(
            'data-candidate-group',
            'incidental',
        );
        expect(screen.getByText('mod_archive.release.candidate_audit_only')).toBeInTheDocument();
    });

    it('renders nothing when an older release has no candidate policy fields', () => {
        const rows = getTraceabilityRows([{
            aggregate: { aggregate_key: 'entity:legacy', aggregate_type: 'entity' },
            contributions: [{ source_item: { source_ref: 'legacy::1' } }],
        }]);

        renderSection(rows);
        expect(screen.queryByTestId('mod-archive-candidate-governance')).not.toBeInTheDocument();
    });
});

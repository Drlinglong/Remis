import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import EntityEvidenceDetails from './EntityEvidenceDetails';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key, options) => options?.defaultValue || key }),
}));

const t = (key, options) => options?.defaultValue || key;

const entry = {
    aggregate_id: 'entity-1',
    aggregate_type: 'entity',
    label: 'The entity',
    summary: 'The final LLM digest.',
    payload: {
        tier: 'secondary',
        evidence_complete: true,
        evidence: [
            { fragment_id: 'fragment-1', local_description: 'First local description.', digest_segment_id: 'segment-1' },
            { fragment_id: 'fragment-2', local_description: 'Second local description.', digest_segment_id: 'segment-2' },
        ],
        mechanical_local_description: 'First local description.\n\nSecond local description.',
        partial_digests: [{ digest_segment_id: 'segment-1', partial_digest: 'First partial digest.' }],
    },
};

describe('EntityEvidenceDetails', () => {
    it('shows all evidence and digest comparisons only in the advanced detail component', () => {
        render(
            <MantineProvider>
                <EntityEvidenceDetails entry={entry} preview={{ entries: [entry] }} t={t} />
            </MantineProvider>,
        );

        expect(screen.getByTestId('entity-evidence-all')).toHaveTextContent('2');
        expect(screen.getByTestId('entity-evidence-mechanical')).toHaveTextContent('First local description.');
        expect(screen.getByTestId('entity-evidence-final-digest')).toHaveTextContent('The final LLM digest.');
        expect(screen.getByText('First local description.')).toBeInTheDocument();
        expect(screen.getByText('Second local description.')).toBeInTheDocument();
        expect(screen.getAllByText(/digest_segment_id/)).toHaveLength(3);
    });

    it('states that C-level candidates have no generated digest', () => {
        render(
            <MantineProvider>
                <EntityEvidenceDetails
                    entry={{ ...entry, payload: { ...entry.payload, tier: 'incidental' } }}
                    preview={{ entries: [entry] }}
                    t={t}
                />
            </MantineProvider>,
        );

        expect(screen.getByTestId('entity-evidence-no-summary')).toHaveTextContent('C-level');
        expect(screen.queryByTestId('entity-evidence-final-digest')).not.toBeInTheDocument();
        expect(screen.getByTestId('entity-evidence-all')).toBeInTheDocument();
    });
});

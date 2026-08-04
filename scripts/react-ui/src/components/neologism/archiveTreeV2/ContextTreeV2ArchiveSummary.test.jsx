import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ContextTreeV2ArchiveSummary from './ContextTreeV2ArchiveSummary';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key, options = {}) => options.defaultValue || key }),
}));
vi.mock('./ContextArchiveTreeReview', () => ({
    default: () => <div data-testid="tree-v2-review" />,
}));

const tree = {
    project_id: 'project-1',
    tree_id: 'tree-1',
    project_title: 'Toxic God',
    project_summary: 'Project summary.',
    stories: [{ story_id: 'story-1', group_ids: ['group-1'] }],
    groups: [{
        group_id: 'group-1',
        title: 'First quest',
        fragment_ids: ['fragment-1', 'fragment-2'],
    }],
    local_fragments: [
        { fragment_id: 'fragment-1', summary: 'The knight accepts the quest.' },
        { fragment_id: 'fragment-2', summary: 'The knight resolves the quest.' },
    ],
    candidates: [
        {
            candidate_id: 'entity-knight',
            candidate_kind: 'entity',
            canonical_display_name: 'Knight',
            tier: 'A',
            summary_eligible: true,
            mention_count: 8,
            local_unit_coverage: 4,
            event_group_coverage: 2,
            raw_chunk_contributions: [{ batch_index: 1, surface: 'the knight' }],
        },
        {
            candidate_id: 'entity-zeta',
            candidate_kind: 'entity',
            canonical_display_name: 'Zeta',
            tier: 'C',
            summary_eligible: false,
        },
    ],
    entity_digests: [{ entity_id: 'entity-knight', final_digest: 'A/B entity summary.' }],
    entity_evidence: [{
        evidence_id: 'evidence-1',
        entity_id: 'entity-knight',
        batch_id: 'chunk-1',
        item_key: 'key-1',
        full_source_text: 'The Knight accepts the quest.',
    }],
};

describe('ContextTreeV2ArchiveSummary', () => {
    it('shows mechanical event bullets and A/B entities while folding C by default', () => {
        render(<MantineProvider><ContextTreeV2ArchiveSummary tree={tree} mode="published" /></MantineProvider>);

        expect(screen.getByText('• The knight accepts the quest.')).toBeInTheDocument();
        expect(screen.getByText('• The knight resolves the quest.')).toBeInTheDocument();
        expect(screen.getByText('A/B entity summary.')).toBeInTheDocument();
        expect(screen.getByText(/C \/ unclassified entities/).closest('details')).not.toHaveAttribute('open');

        fireEvent.click(screen.getByRole('switch', { name: 'advanced_options' }));
        expect(screen.getByText('The Knight accepts the quest.')).toBeInTheDocument();
        expect(screen.getByTestId('tree-v2-review')).toBeInTheDocument();
    });
});

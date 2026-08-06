import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ContextTreeV2ArchiveSummary from './ContextTreeV2ArchiveSummary';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key, options = {}) => options.defaultValue || key }),
}));

const tree = {
    project_id: 'project-1',
    tree_id: 'tree-1',
    release_id: 'release-1',
    project_title: 'Toxic God',
    project_summary: 'Project summary.',
    units: [
        { unit_id: 'unit-1', label: 'Opening', source_ref: 'events/opening.yml:1', source_text: 'The knight accepts the quest.' },
        { unit_id: 'unit-2', label: 'Resolution', source_ref: 'events/resolution.yml:4', source_text: 'The knight resolves the quest.' },
    ],
    stories: [{ story_id: 'story-1', group_ids: ['group-1', 'group-2'] }],
    groups: [
        { group_id: 'group-1', title: 'First quest', fragment_ids: ['fragment-1', 'fragment-2'] },
        { group_id: 'group-2', title: 'Second quest', fragment_ids: [] },
    ],
    fragments: [
        { fragment_id: 'fragment-1', label: 'Accepts the quest', summary: 'Opening summary.', unit_ids: ['unit-1'] },
        { fragment_id: 'fragment-2', label: 'Resolves the quest', summary: 'Resolution summary.', unit_ids: ['unit-2'] },
    ],
    candidates: [
        { candidate_id: 'entity-knight', candidate_kind: 'entity', canonical_display_name: 'Knight', tier: 'A', mention_count: 8, local_unit_coverage: 4, summary: 'A/B entity summary.' },
        { candidate_id: 'entity-zeta', candidate_kind: 'entity', canonical_display_name: 'Zeta', tier: 'C', mention_count: 1 },
    ],
    entity_evidence: [{ evidence_id: 'evidence-1', entity_id: 'entity-knight', source_ref: 'events/opening.yml:1', excerpt: 'The Knight accepts the quest.' }],
};

const renderSummary = (value = tree) => render(
    <MantineProvider><ContextTreeV2ArchiveSummary tree={value} mode="published" /></MantineProvider>,
);

describe('ContextTreeV2ArchiveSummary', () => {
    it('starts with a compact relationship map and folds the other entities', () => {
        renderSummary();

        expect(screen.getByTestId('published-context-map')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-detail-empty')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-project-root')).toHaveTextContent('Toxic God');
        expect(screen.getByTestId('published-context-group-group-1')).toHaveTextContent('First quest');
        expect(screen.getByTestId('published-context-map')).not.toHaveTextContent('Resolution summary.');
        expect(screen.getByText('A/B entity summary.')).toBeInTheDocument();
        expect(screen.getByText(/Other entities/).closest('details')).not.toHaveAttribute('open');
        expect(screen.queryByRole('switch')).not.toBeInTheDocument();
    });

    it('shows the selected fragment source detail and supports moving a card between chains', () => {
        renderSummary();

        fireEvent.click(screen.getByTestId('published-context-fragment-fragment-2'));
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('Resolves the quest');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('events/resolution.yml:4');
        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-view', 'focused');

        const dataTransfer = { setData: vi.fn(), effectAllowed: 'none', getData: () => 'fragment-2' };
        fireEvent.click(screen.getByRole('button', { name: 'Back to overview' }));
        fireEvent.dragStart(screen.getByTestId('published-context-fragment-fragment-2'), { dataTransfer });
        fireEvent.drop(screen.getByTestId('published-context-group-group-2'), { dataTransfer });

        expect(screen.getByTestId('published-context-group-group-2')).toHaveTextContent('Resolves the quest');
        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-remis-surface', 'surface');
    });

    it('keeps all top-level chains on one dynamic relationship rail', () => {
        const groupIds = ['group-1', 'group-2', 'group-3', 'group-4', 'group-5', 'group-6'];
        const manyChains = {
            ...tree,
            stories: [{ ...tree.stories[0], group_ids: groupIds }],
            groups: [
                ...tree.groups,
                ...groupIds.slice(2).map((groupId, index) => ({
                    group_id: groupId,
                    title: `Quest branch ${index + 3}`,
                    fragment_ids: [],
                })),
            ],
        };

        renderSummary(manyChains);

        const map = screen.getByTestId('published-context-map');
        const grid = map.querySelector('[style*="--chain-count"]');
        expect(grid).toHaveStyle('--chain-count: 6');
        expect(screen.getByTestId('published-context-group-group-6')).toBeInTheDocument();
    });

    it('creates a named event chain from the overview entry point', () => {
        renderSummary();

        fireEvent.click(screen.getByRole('button', { name: 'Add event chain' }));
        const input = screen.getByRole('textbox', { name: 'New event chain' });
        fireEvent.change(input, { target: { value: 'New route' } });
        fireEvent.submit(input.closest('form'));

        expect(screen.getByTestId('published-context-group-group-new-route')).toHaveTextContent('New route');
    });

    it('confirms deletion of the selected event chain and returns to the overview', () => {
        renderSummary();

        fireEvent.click(screen.getByTestId('published-context-group-header-group-1'));
        fireEvent.click(screen.getByRole('button', { name: 'Delete event chain' }));
        fireEvent.click(screen.getByRole('button', { name: 'Delete chain' }));

        expect(screen.queryByTestId('published-context-group-group-1')).not.toBeInTheDocument();
        expect(screen.getByTestId('published-context-detail-empty')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-view', 'overview');
    });
});

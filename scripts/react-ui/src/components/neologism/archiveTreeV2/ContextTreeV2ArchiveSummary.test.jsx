import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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

beforeEach(() => {
    window.matchMedia.mockImplementation((query) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }));
});

describe('ContextTreeV2ArchiveSummary', () => {
    it('starts with a compact relationship map and folds the other entities', () => {
        renderSummary();

        expect(screen.getByTestId('published-context-map')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-detail-empty')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-project-root')).toHaveTextContent('Toxic God');
        expect(screen.getByTestId('published-context-group-group-1')).toHaveTextContent('First quest');
        expect(screen.getByTestId('published-context-map')).not.toHaveTextContent('Resolution summary.');
        expect(screen.getByText('A/B entity summary.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Entities/ })).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText(/Other entities/).closest('details')).not.toHaveAttribute('open');
        expect(screen.queryByRole('switch')).not.toBeInTheDocument();
    });

    it('collapses and restores the entity section without persisting hidden state', () => {
        const { unmount } = renderSummary();
        const toggle = screen.getByRole('button', { name: /Entities/ });
        const content = document.getElementById(toggle.getAttribute('aria-controls'));

        fireEvent.click(toggle);
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(content).toHaveAttribute('data-expanded', 'false');
        expect(content).toHaveAttribute('aria-hidden', 'true');
        expect(content).toHaveAttribute('inert');

        fireEvent.click(toggle);
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(content).toHaveAttribute('data-expanded', 'true');
        expect(content).toHaveAttribute('aria-hidden', 'false');
        expect(content).not.toHaveAttribute('inert');

        unmount();
        renderSummary();
        expect(screen.getByRole('button', { name: /Entities/ })).toHaveAttribute('aria-expanded', 'true');
    });

    it('shows the selected fragment source detail and keeps dragging on dnd-kit', () => {
        renderSummary();

        fireEvent.click(screen.getByTestId('published-context-fragment-fragment-2'));
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('Resolves the quest');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('events/resolution.yml:4');
        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-view', 'focused');

        const sourceDetails = screen.getByText('events/resolution.yml:4').closest('details');
        expect(sourceDetails).not.toHaveAttribute('open');
        fireEvent.click(sourceDetails.querySelector('summary'));
        expect(sourceDetails).toHaveAttribute('open');

        expect(screen.getByTestId('published-context-fragment-fragment-2')).not.toHaveAttribute('draggable');
        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-remis-surface', 'surface');
    });

    it('keeps supporting text quiet and needs-placement cards last', () => {
        const classifiedTree = {
            ...tree,
            fragments: [
                ...tree.fragments,
                { fragment_id: 'fragment-reference', label: 'Reference note', route: 'reference' },
                { fragment_id: 'fragment-unassigned', label: 'Loose event', route: 'narrative' },
                { fragment_id: 'fragment-unresolved', label: 'Unresolved event', route: 'unresolved' },
            ],
            reference_assets: [{ id: 'asset-reference', fragment_id: 'fragment-reference', label: 'Reference note' }],
        };

        renderSummary(classifiedTree);

        const supporting = screen.getByTestId('published-context-group-group-support');
        const needsPlacement = screen.getByTestId('published-context-group-group-unassigned');
        expect(supporting).toHaveAttribute('data-group-kind', 'supporting');
        expect(needsPlacement).toHaveAttribute('data-group-kind', 'needs-placement');
        expect(needsPlacement).toHaveTextContent('Loose event');
        expect(needsPlacement).toHaveTextContent('Unresolved event');
        expect(needsPlacement.parentElement.lastElementChild).toBe(needsPlacement);
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

    it('keeps other event chains available as focused droppable rails', () => {
        renderSummary();

        fireEvent.click(screen.getByTestId('published-context-group-header-group-1'));
        const rail = screen.getByTestId('published-context-mini-rail-group-2');
        expect(rail).toHaveAttribute('data-drop-target', 'group:group-2');
        expect(rail).toHaveTextContent('Second quest');

        fireEvent.click(rail);
        expect(screen.getByTestId('published-context-map')).toHaveTextContent('Second quest');
        expect(screen.getByTestId('published-context-mini-rail-group-1')).toBeInTheDocument();
    });

    it('renames the focused event chain inline and cancels a later draft with Escape', () => {
        renderSummary();

        fireEvent.click(screen.getByTestId('published-context-group-header-group-1'));
        fireEvent.click(screen.getByRole('button', { name: 'Rename event chain' }));
        const input = screen.getByRole('textbox', { name: 'Event chain name' });
        fireEvent.change(input, { target: { value: 'Opening route' } });
        fireEvent.keyDown(input, { key: 'Enter' });

        expect(screen.getByTestId('published-context-group-group-1')).toHaveTextContent('Opening route');
        expect(screen.getByText('Unsaved relationship changes')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Rename event chain' }));
        const secondDraft = screen.getByRole('textbox', { name: 'Event chain name' });
        fireEvent.change(secondDraft, { target: { value: 'Discarded name' } });
        fireEvent.keyDown(secondDraft, { key: 'Escape' });
        expect(screen.getByTestId('published-context-group-group-1')).toHaveTextContent('Opening route');
        expect(screen.getByTestId('published-context-group-group-1')).not.toHaveTextContent('Discarded name');
    });

    it('routes the selected fragment through the existing disposition controller', () => {
        renderSummary();

        fireEvent.click(screen.getByTestId('published-context-fragment-fragment-1'));
        fireEvent.change(screen.getByRole('combobox', { name: 'Delivery role' }), {
            target: { value: 'reference_asset' },
        });

        expect(screen.getByTestId('published-context-group-group-support')).toHaveTextContent('Accepts the quest');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('reference_asset');
        expect(screen.getByText('Unsaved relationship changes')).toBeInTheDocument();
    });
});

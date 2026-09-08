import React from 'react';
import {
    fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import ContextTreeV2ArchiveSummary from './ContextTreeV2ArchiveSummary';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key, options = {}) => options.defaultValue || key }),
}));

const buildTree = (fragmentCount = 2) => ({
    project_id: 'layout-project',
    release_id: 'layout-release',
    project_title: 'Layout fixture',
    units: Array.from({ length: fragmentCount }, (_, index) => ({
        unit_id: `unit-${index + 1}`,
        source_ref: `events/step-${index + 1}.yml:1`,
        source_text: `Source ${index + 1}`,
    })),
    stories: [{ story_id: 'story-layout', group_ids: ['group-layout'] }],
    groups: [{
        group_id: 'group-layout',
        title: 'A long event chain',
        fragment_ids: Array.from({ length: fragmentCount }, (_, index) => `fragment-${index + 1}`),
    }],
    fragments: Array.from({ length: fragmentCount }, (_, index) => ({
        fragment_id: `fragment-${index + 1}`,
        label: `Step ${index + 1}`,
        summary: `Summary ${index + 1}`,
        unit_ids: [`unit-${index + 1}`],
    })),
});

const renderSummary = (fragmentCount) => render(
    <MantineProvider>
        <ContextTreeV2ArchiveSummary tree={buildTree(fragmentCount)} mode="published" />
    </MantineProvider>,
);

beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    window.matchMedia.mockImplementation((query) => ({
        matches: query === '(prefers-reduced-motion: reduce)' || query === '(max-width: 52em)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }));
});

describe('Published context archive layout', () => {
    it('does not add a preview control for a group with six or fewer cards', () => {
        renderSummary(6);

        expect(screen.queryByTestId('published-context-view-all-group-layout')).not.toBeInTheDocument();
        expect(screen.getByTestId('published-context-fragment-fragment-6')).toBeVisible();
    });

    it('previews six cards and keeps every focused card draggable', async () => {
        renderSummary(8);

        const viewAll = screen.getByTestId('published-context-view-all-group-layout');
        expect(screen.getByTestId('published-context-fragment-fragment-6')).toBeVisible();
        expect(screen.queryByTestId('published-context-fragment-fragment-7')).not.toBeInTheDocument();
        expect(viewAll).toHaveTextContent('View all 8 items (2 more)');
        expect(viewAll).not.toHaveAttribute('aria-expanded');
        expect(viewAll).toHaveAttribute('aria-controls', 'published-context-detail');

        fireEvent.click(viewAll);

        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-view', 'focused');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('Step 8');
        expect(screen.getByTestId('published-context-chain-detail-list').querySelectorAll('button')).toHaveLength(8);
        const eighthCard = screen.getByTestId('published-context-fragment-fragment-8');
        expect(eighthCard).toBeVisible();
        expect(eighthCard).toHaveAttribute('aria-roledescription', 'draggable');
        await waitFor(() => expect(screen.getByTestId('published-context-detail')).toHaveFocus());
    });

    it('keeps card selection connected to the existing event detail', () => {
        renderSummary(8);

        fireEvent.click(screen.getByTestId('published-context-fragment-fragment-2'));

        expect(screen.getByTestId('published-context-map')).toHaveAttribute('data-view', 'focused');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('Step 2');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('events/step-2.yml:1');
    });

    it('renders release evidence when published fragments only expose local unit ids', () => {
        const tree = buildTree(1);
        delete tree.units;
        tree.fragments[0].source_evidence_refs = [{
            source_item_id: 'source-item-title',
            source_ref: 'localisation/english/events.yml',
            local_unit_id: 'unit-1',
            item_key: 'event.1.name:0',
            source_order: 10,
            full_source_text: 'The Hundred Years Quest',
        }, {
            source_item_id: 'source-item-desc',
            source_ref: 'localisation/english/events.yml',
            local_unit_id: 'unit-1',
            item_key: 'event.1.desc:0',
            source_order: 11,
            full_source_text: 'One hundred years ago, we took to the stars.',
        }];
        render(
            <MantineProvider>
                <ContextTreeV2ArchiveSummary tree={tree} mode="published" />
            </MantineProvider>,
        );

        fireEvent.click(screen.getByTestId('published-context-fragment-fragment-1'));

        const detail = screen.getByTestId('published-context-detail');
        expect(detail).toHaveTextContent('localisation/english/events.yml::event.1.name:0');
        expect(detail).toHaveTextContent('The Hundred Years Quest');
        expect(detail).toHaveTextContent('One hundred years ago, we took to the stars.');
        expect(detail).not.toHaveTextContent('Source text is unavailable for this unit.');
    });

    it('expands and collapses long non-event collections', () => {
        const tree = buildTree(2);
        tree.fragments = [
            ...tree.fragments,
            ...Array.from({ length: 7 }, (_, index) => ({
                fragment_id: `reference-${index + 1}`,
                label: `Reference ${index + 1}`,
                unit_ids: [],
                route: 'reference',
            })),
        ];
        tree.reference_assets = Array.from({ length: 7 }, (_, index) => ({
            id: `reference-asset-${index + 1}`,
            fragment_id: `reference-${index + 1}`,
            label: `Reference ${index + 1}`,
        }));
        render(
            <MantineProvider>
                <ContextTreeV2ArchiveSummary tree={tree} mode="published" />
            </MantineProvider>,
        );

        const viewAll = screen.getByTestId('published-context-view-all-group-support');
        expect(screen.queryByTestId('published-context-fragment-reference-7')).not.toBeInTheDocument();
        expect(viewAll).toHaveAttribute('aria-controls', 'published-context-fragments-group-support');
        fireEvent.click(viewAll);

        expect(screen.getByTestId('published-context-fragment-reference-7')).toBeVisible();
        expect(screen.getByTestId('published-context-fragments-group-support'))
            .toHaveAttribute('data-preview-expanded', 'true');
        expect(viewAll).toHaveAttribute('aria-expanded', 'true');
        expect(viewAll).toHaveTextContent('Show fewer items');

        fireEvent.click(viewAll);

        expect(screen.queryByTestId('published-context-fragment-reference-7')).not.toBeInTheDocument();
        expect(viewAll).toHaveAttribute('aria-expanded', 'false');
        expect(viewAll).toHaveTextContent('View all 7 items (1 more)');
    });

    it('hands focus to stacked details and restores the originating control on return', async () => {
        renderSummary(8);
        const viewAll = screen.getByTestId('published-context-view-all-group-layout');

        fireEvent.click(viewAll);

        const detail = screen.getByTestId('published-context-detail');
        await waitFor(() => expect(detail).toHaveFocus());
        expect(detail.scrollIntoView).toHaveBeenCalledWith({
            block: 'start',
            inline: 'nearest',
            behavior: 'auto',
        });

        fireEvent.click(within(detail).getByRole('button', { name: 'Back to map' }));

        const restoredViewAll = await screen.findByTestId('published-context-view-all-group-layout');
        await waitFor(() => expect(restoredViewAll).toHaveFocus());
        expect(restoredViewAll.scrollIntoView).toHaveBeenCalled();
    });
});

describe('Published context layout CSS contract', () => {
    it('top-aligns sibling columns and gives the full detail panel its own scroll boundary', () => {
        const styles = readFileSync(resolve(
            process.cwd(),
            'src/components/neologism/archiveTreeV2/PublishedContextWorkbench.module.css',
        ), 'utf8');

        expect(styles).toMatch(/\.groupGrid\s*\{[\s\S]*?align-items:\s*start;/);
        expect(styles).toMatch(/\.groupColumn\s*\{[\s\S]*?align-self:\s*start;/);
        expect(styles).toMatch(/\.focusedGroupStage\s*\{[\s\S]*?align-items:\s*flex-start;/);
        expect(styles).toMatch(/\.detailPanel\s*\{[\s\S]*?max-height:[\s\S]*?overflow-y:\s*auto;/);
        expect(styles).toMatch(/\.expandedFragmentList,\s*\.focusedFragmentList\s*\{[\s\S]*?max-height:[\s\S]*?overflow-y:\s*auto;/);
    });
});

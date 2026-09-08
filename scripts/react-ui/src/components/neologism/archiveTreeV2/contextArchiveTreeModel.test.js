import { describe, expect, it } from 'vitest';

import {
    buildNarrativeUnitPreview,
    groupReferenceAssetsByTier,
    normalizeArchiveTree,
} from './contextArchiveTreeModel';
import { treeFixture } from './contextArchiveTreeFixture';

describe('context archive tree model', () => {
    it('normalizes stories, sibling groups, ordered fragments, and explicit routes', () => {
        const tree = normalizeArchiveTree(treeFixture);

        expect(tree.available).toBe(true);
        expect(tree.stories[0].groupIds).toEqual(['group-arrival', 'group-choice']);
        expect(tree.groups[0].fragmentIds).toEqual(['fragment-1', 'fragment-2']);
        expect(tree.fragments['fragment-4'].route).toBe('reference_asset');
        expect(tree.unresolvedFragmentIds).toEqual(['fragment-3']);
        expect(tree.referenceAssets.map((asset) => asset.label)).toEqual(['Alpha', 'A named asset', 'Zeta']);
    });

    it('builds the final event context from the group order and keeps reference assets out', () => {
        const tree = normalizeArchiveTree(treeFixture);
        const preview = buildNarrativeUnitPreview(tree, 'unit-1');

        expect(preview.hasEventContext).toBe(true);
        expect(preview.groups[0].bullets).toEqual(['The expedition arrives.', 'The gate opens.']);
        expect(buildNarrativeUnitPreview(tree, 'unit-2').groups).toEqual([]);
    });

    it('sorts A and B assets before C and leaves C collapsed by default', () => {
        const tree = normalizeArchiveTree(treeFixture);
        const buckets = groupReferenceAssetsByTier(tree.referenceAssets);

        expect(buckets.map((bucket) => bucket.tier)).toEqual(['A', 'C']);
        expect(buckets[0].openByDefault).toBe(true);
        expect(buckets[1].openByDefault).toBe(false);
    });

    it('keeps archive-only narratives visible without treating them as unresolved delivery', () => {
        const tree = normalizeArchiveTree({
            project_id: 'archive-only-test',
            archive_narratives: [{
                fragment_id: 'archive-lore',
                label: 'World background',
                summary: 'Useful project lore, not a concrete event.',
                unit_ids: ['unit-lore'],
                route: 'no_context',
                metadata: { delivery_target: false },
            }],
            units: [{ unit_id: 'unit-lore', label: 'Lore', route: 'no_context' }],
        });

        expect(tree.available).toBe(true);
        expect(tree.archiveNarrativeIds).toEqual(['archive-lore']);
        expect(tree.unresolvedFragmentIds).toEqual([]);
        expect(buildNarrativeUnitPreview(tree, 'unit-lore').hasEventContext).toBe(false);
    });

    it('keeps published fragment source evidence when the release omits expanded units', () => {
        const tree = normalizeArchiveTree({
            project_id: 'published-evidence-test',
            stories: [{ story_id: 'story-1', group_ids: ['group-1'] }],
            groups: [{ group_id: 'group-1', fragment_ids: ['fragment-1'] }],
            local_fragments: [{
                fragment_id: 'fragment-1',
                unit_ids: ['unit_171'],
                source_evidence_refs: [{
                    source_item_id: 'source-item-title',
                    source_ref: 'localisation/english/events.yml',
                    local_unit_id: 'unit_171',
                    item_key: 'event.1.name:0',
                    source_order: 10,
                    full_source_text: 'The Hundred Years Quest',
                }, {
                    source_item_id: 'source-item-desc',
                    source_ref: 'localisation/english/events.yml',
                    local_unit_id: 'unit_171',
                    item_key: 'event.1.desc:0',
                    source_order: 11,
                    full_source_text: 'One hundred years ago, we took to the stars.',
                }],
            }],
        });

        expect(tree.fragments['fragment-1'].sourceEvidence).toEqual([
            expect.objectContaining({
                localUnitId: 'unit_171',
                label: 'localisation/english/events.yml::event.1.name:0',
                text: 'The Hundred Years Quest',
            }),
            expect.objectContaining({
                localUnitId: 'unit_171',
                label: 'localisation/english/events.yml::event.1.desc:0',
                text: 'One hundred years ago, we took to the stars.',
            }),
        ]);
    });
});

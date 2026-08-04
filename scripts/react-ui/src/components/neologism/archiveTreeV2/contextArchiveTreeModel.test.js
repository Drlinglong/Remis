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
});

import { describe, expect, it } from 'vitest';

import {
    createGroup,
    createStory,
    deleteGroup,
    moveFragment,
    renameGroup,
    renameStory,
    reorderFragment,
    serializeArchiveTree,
    setFragmentDisposition,
} from './contextArchiveTreeController';
import { normalizeArchiveTree } from './contextArchiveTreeModel';
import { treeFixture } from './contextArchiveTreeFixture';

const makeTree = () => normalizeArchiveTree(treeFixture);

describe('context archive tree controller', () => {
    it('moves fragments across groups without mutating the source tree', () => {
        const tree = makeTree();
        const next = moveFragment(tree, {
            fragmentId: 'fragment-2',
            targetGroupId: 'group-choice',
        });

        expect(tree.groups[0].fragmentIds).toEqual(['fragment-1', 'fragment-2']);
        expect(next.groups[0].fragmentIds).toEqual(['fragment-1']);
        expect(next.groups[1].fragmentIds).toEqual(['fragment-2']);
        expect(next.unresolvedFragmentIds).toEqual(['fragment-3']);
    });

    it('reorders fragments within one group using the controller seam', () => {
        const next = reorderFragment(makeTree(), {
            fragmentId: 'fragment-2',
            groupId: 'group-arrival',
            index: 0,
        });

        expect(next.groups[0].fragmentIds).toEqual(['fragment-2', 'fragment-1']);
    });

    it('creates and renames containers while preserving stable IDs', () => {
        const tree = makeTree();
        const withStory = createStory(tree, { label: 'Side path' });
        const storyId = withStory.stories[1].id;
        const withGroup = createGroup(withStory, { storyId, label: 'Side events' });
        const groupId = withGroup.groups[2].id;
        const renamed = renameGroup(renameStory(withGroup, storyId, 'Alternate path'), groupId, 'Branch events');

        expect(renamed.stories[1].label).toBe('Alternate path');
        expect(renamed.groups[2].label).toBe('Branch events');
        expect(renamed.stories[1].groupIds).toEqual([groupId]);
    });

    it('routes a fragment to reference asset or unresolved without deleting evidence IDs', () => {
        const tree = makeTree();
        const reference = setFragmentDisposition(tree, 'fragment-1', 'reference_asset');
        const unresolved = setFragmentDisposition(reference, 'fragment-4', 'unresolved');

        expect(reference.groups[0].fragmentIds).toEqual(['fragment-2']);
        expect(reference.referenceAssets.some((asset) => asset.fragmentId === 'fragment-1')).toBe(true);
        expect(reference.fragments['fragment-1'].evidenceIds).toEqual([]);
        expect(unresolved.fragments['fragment-4'].route).toBe('unresolved');
        expect(unresolved.unresolvedFragmentIds).toContain('fragment-4');
    });

    it('re-homes deleted group fragments as unresolved and serializes only relation fields', () => {
        const tree = makeTree();
        const next = deleteGroup(tree, 'group-arrival');
        const payload = serializeArchiveTree(next);

        expect(next.unresolvedFragmentIds).toEqual(['fragment-3', 'fragment-1', 'fragment-2']);
        expect(payload.groups).toEqual([{ group_id: 'group-choice', story_id: 'story-main', label: 'Choice', fragment_ids: [] }]);
        expect(payload.fragments[0]).toMatchObject({ fragment_id: 'fragment-1', route: 'narrative' });
    });
});

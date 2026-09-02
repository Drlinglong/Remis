import { describe, expect, it } from 'vitest';

import { normalizeArchiveTree } from './contextArchiveTreeModel';

describe('context archive display labels', () => {
    it('replaces identifier echoes with concise summary labels', () => {
        const tree = normalizeArchiveTree({
            project_id: 'toxic-god',
            project_title: '毒圣骑士测试',
            stories: [{
                story_id: 'story_main',
                title: 'story_main',
                group_ids: ['group_toxin_defeat'],
            }],
            groups: [{
                group_id: 'group_toxin_defeat',
                title: 'group_toxin_defeat',
                summary: '- 骑士团击败有毒实体，随后决定如何处置。\n- 骑士团重新选择未来。',
                fragment_ids: ['fragment_c6_6'],
            }],
            local_fragments: [{
                fragment_id: 'fragment_c6_6',
                summary: '骑士团击败有毒实体，随后在控制、崇拜或杀死之间作出选择。',
                unit_ids: ['unit_165'],
            }],
        });

        expect(tree.stories[0].label).toBe('毒圣骑士测试');
        expect(tree.groups[0].label).toBe('骑士团击败有毒实体');
        expect(tree.fragments.fragment_c6_6.label).toBe('骑士团击败有毒实体');
    });

    it('preserves an explicit human-authored label', () => {
        const tree = normalizeArchiveTree({
            project_title: 'Test project',
            stories: [{ story_id: 'story_main', group_ids: ['group_1'] }],
            groups: [{
                group_id: 'group_1',
                title: '毒神之战与骑士团抉择',
                summary: 'A different summary.',
                fragment_ids: [],
            }],
        });

        expect(tree.groups[0].label).toBe('毒神之战与骑士团抉择');
    });
});

export const treeFixture = {
    schema_version: 'context-tree-v2',
    project_id: 'project-1',
    project_summary: 'A project about a divided expedition.',
    units: [
        { unit_id: 'unit-1', label: 'Opening', route: 'narrative' },
        { unit_id: 'unit-2', label: 'Asset name', route: 'reference_asset' },
    ],
    stories: [{ story_id: 'story-main', label: 'Expedition', group_ids: ['group-arrival', 'group-choice'] }],
    groups: [
        {
            group_id: 'group-arrival',
            story_id: 'story-main',
            label: 'Arrival',
            fragment_ids: ['fragment-1', 'fragment-2'],
        },
        { group_id: 'group-choice', story_id: 'story-main', label: 'Choice', fragment_ids: [] },
    ],
    fragments: [
        { fragment_id: 'fragment-1', label: 'First beat', summary: 'The expedition arrives.', unit_ids: ['unit-1'], route: 'narrative' },
        { fragment_id: 'fragment-2', label: 'Second beat', summary: 'The gate opens.', unit_ids: ['unit-1'], route: 'narrative' },
        { fragment_id: 'fragment-3', label: 'Loose beat', summary: 'Needs review.', unit_ids: ['unit-1'], route: 'narrative' },
        { fragment_id: 'fragment-4', label: 'A named asset', summary: 'A stable name.', unit_ids: ['unit-2'], route: 'reference_asset', tier: 'A' },
    ],
    reference_assets: [
        { asset_id: 'asset-z', label: 'Zeta', tier: 'C' },
        { asset_id: 'asset-a', label: 'Alpha', tier: 'A' },
    ],
};

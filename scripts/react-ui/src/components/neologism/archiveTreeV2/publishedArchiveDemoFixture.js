export const PUBLISHED_ARCHIVE_DEMO_PROJECT_ID = 'demo-starport-expedition';
export const PUBLISHED_ARCHIVE_DEMO_RELEASE_ID = 'release-demo-2026-08-05';

export const publishedArchiveDemoProject = {
    project_id: PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    name: '星港远征：失落航道（演示项目）',
    label: '星港远征：失落航道（演示项目）',
    is_demo: true,
};

export const publishedArchiveDemoRelease = {
    release_id: PUBLISHED_ARCHIVE_DEMO_RELEASE_ID,
    project_id: PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    created_at: '2026-08-05T12:00:00Z',
    metadata: { created_at: '2026-08-05T12:00:00Z' },
};

export const publishedArchiveDemoTree = {
    schema_version: 'context-tree-v2',
    tree_id: 'tree-demo-starport-expedition',
    release_id: PUBLISHED_ARCHIVE_DEMO_RELEASE_ID,
    project_id: PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    project_title: '星港远征：失落航道',
    project_summary: '一支远征队在失落航道发现旧星港，并在返航与继续探索之间做出选择。',
    units: [
        {
            unit_id: 'unit-arrival',
            label: '抵达星港',
            route: 'narrative',
            source_ref: 'events/starport_expedition.yml:12',
            source_text: '远征队在磁暴减弱后抵达失落星港，入口仍然保持供能。',
        },
        {
            unit_id: 'unit-signal',
            label: '发现信标',
            route: 'narrative',
            source_ref: 'events/starport_expedition.yml:27',
            source_text: '导航官林岚从废弃信标中解读出一段仍在重复的求救讯号。',
        },
        {
            unit_id: 'unit-vote',
            label: '返航表决',
            route: 'narrative',
            source_ref: 'events/starport_expedition.yml:41',
            source_text: '舰长顾沉要求全员表决：带着样本返航，或进入尚未标记的内环。',
        },
        {
            unit_id: 'unit-relic',
            label: '航道遗物',
            route: 'reference_asset',
            source_ref: 'common/starport_assets.yml:8',
            source_text: '旧式跃迁罗盘，表面刻有失落航道的环形坐标。',
        },
    ],
    stories: [{
        story_id: 'story-expedition',
        label: '失落航道调查',
        group_ids: ['group-arrival', 'group-signal', 'group-decision'],
    }],
    groups: [
        {
            group_id: 'group-arrival',
            story_id: 'story-expedition',
            label: '抵达星港',
            summary: '远征队进入旧设施。',
            fragment_ids: ['fragment-arrival', 'fragment-gate'],
        },
        {
            group_id: 'group-signal',
            story_id: 'story-expedition',
            label: '信标回响',
            summary: '讯号将调查引向内环。',
            fragment_ids: ['fragment-signal', 'fragment-map'],
        },
        {
            group_id: 'group-decision',
            story_id: 'story-expedition',
            label: '返航抉择',
            summary: '队伍决定下一步路线。',
            fragment_ids: ['fragment-vote'],
        },
    ],
    fragments: [
        { fragment_id: 'fragment-arrival', label: '磁暴减弱', summary: '远征队抵达失落星港。', unit_ids: ['unit-arrival'], route: 'narrative' },
        { fragment_id: 'fragment-gate', label: '入口仍在供能', summary: '旧星港入口没有完全断电。', unit_ids: ['unit-arrival'], route: 'narrative' },
        { fragment_id: 'fragment-signal', label: '解读求救讯号', summary: '林岚确认信标正在重复发送求救讯号。', unit_ids: ['unit-signal'], route: 'narrative' },
        { fragment_id: 'fragment-map', label: '发现内环坐标', summary: '讯号中藏着一组未标记的内环坐标。', unit_ids: ['unit-signal'], route: 'narrative' },
        { fragment_id: 'fragment-vote', label: '返航表决', summary: '顾沉让全员在返航与继续探索之间表决。', unit_ids: ['unit-vote'], route: 'narrative' },
        { fragment_id: 'fragment-relic', label: '跃迁罗盘', summary: '一件可复用的航道遗物。', unit_ids: ['unit-relic'], route: 'reference_asset', tier: 'A' },
        { fragment_id: 'fragment-unresolved', label: '未归位航标', summary: '这条航标告警尚未确认所属事件链。', unit_ids: ['unit-signal'], route: 'unresolved' },
    ],
    reference_assets: [
        { asset_id: 'asset-compass', label: '跃迁罗盘', summary: '指向失落航道内环的旧式导航遗物。', tier: 'A', unit_ids: ['unit-relic'] },
        { asset_id: 'asset-beacon', label: '旧星港信标', summary: '持续发送求救讯号的设施。', tier: 'B', unit_ids: ['unit-signal'] },
        { asset_id: 'asset-storm', label: '磁暴', summary: '影响抵达窗口的环境因素。', tier: 'C', unit_ids: ['unit-arrival'] },
    ],
    candidates: [
        { candidate_id: 'entity-gu-chen', candidate_kind: 'entity', canonical_display_name: '顾沉', tier: 'A', mention_count: 12, local_unit_coverage: 4, summary: '远征舰队舰长，负责返航与继续探索的最终决策。' },
        { candidate_id: 'entity-lin-lan', candidate_kind: 'entity', canonical_display_name: '林岚', tier: 'A', mention_count: 8, local_unit_coverage: 3, summary: '导航官，最先识别出信标讯号中的内环坐标。' },
        { candidate_id: 'entity-starport', candidate_kind: 'entity', canonical_display_name: '失落星港', tier: 'B', mention_count: 6, local_unit_coverage: 3, summary: '调查的核心地点，也是旧航道仍然存在的证据。' },
        { candidate_id: 'entity-beacon', candidate_kind: 'entity', canonical_display_name: '求救信标', tier: 'B', mention_count: 4, local_unit_coverage: 2, summary: '将抵达事件与返航抉择连接起来的设施。' },
        { candidate_id: 'entity-storm', candidate_kind: 'entity', canonical_display_name: '磁暴', tier: 'C', mention_count: 1, local_unit_coverage: 1, summary: '低频环境实体。' },
    ],
    entity_evidence: [
        { entity_id: 'entity-gu-chen', source_ref: 'events/starport_expedition.yml:41', excerpt: '舰长顾沉要求全员表决。' },
        { entity_id: 'entity-lin-lan', source_ref: 'events/starport_expedition.yml:27', excerpt: '导航官林岚解读出一段求救讯号。' },
        { entity_id: 'entity-starport', source_ref: 'events/starport_expedition.yml:12', excerpt: '远征队抵达失落星港。' },
    ],
};

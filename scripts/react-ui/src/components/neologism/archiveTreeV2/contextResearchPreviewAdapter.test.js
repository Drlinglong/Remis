import { describe, expect, it } from 'vitest';

import lunaPreview from './lunaContextResearchPreview.json';
import { contextResearchPreviewToArchiveTree } from './contextResearchPreviewAdapter';
import { buildNarrativeUnitPreview, normalizeArchiveTree } from './contextArchiveTreeModel';

describe('context research preview adapter', () => {
    it('projects the normalized Luna draft into the archive workbench without publishing it', () => {
        const rawTree = contextResearchPreviewToArchiveTree(lunaPreview);
        const tree = normalizeArchiveTree(rawTree);

        expect(rawTree.preview_metadata).toMatchObject({
            model: 'openai/gpt-5.6-luna',
            read_only: true,
            published: false,
        });
        expect(tree.groups).toHaveLength(1);
        expect(tree.archiveNarrativeIds).toHaveLength(4);
        expect(tree.referenceAssets).toHaveLength(3);
        expect(tree.unresolvedFragmentIds).toHaveLength(0);
        expect(rawTree.candidates).toEqual(expect.arrayContaining([
            expect.objectContaining({
                candidate_id: 'entity_remis',
                candidate_kind: 'entity',
                canonical_display_name: 'Remis',
                tier: 'A',
            }),
        ]));
        expect(rawTree.candidates.some((candidate) => (
            JSON.stringify(candidate).includes('[Root.GetCapitalName]')
        ))).toBe(false);
        expect(rawTree.unresolved_fragments).toHaveLength(0);
        expect(tree.projectSummary).toMatch(/Remis .*重组银河共和国/);
        expect(tree.projectSummary).toContain('Universal translation context\n');
        expect(tree.projectSummary).not.toContain('事件脉络\n');
        expect(tree.projectSummary).toContain('Pax Remisia');
        expect(tree.projectSummary).not.toContain('未决问题');
        expect(tree.projectSummary).not.toContain('保持未决');
        expect(tree.projectSummary).not.toContain('Luna 将 3 组');

        const eventFragments = tree.groups[0].fragmentIds.map((id) => tree.fragments[id]);
        expect(eventFragments.map((fragment) => fragment.metadata.sequence)).toEqual([1, 2]);
        expect(eventFragments[0].unitIds).toEqual(lunaPreview.draft.event_chains[0].source_item_ids);
        expect(eventFragments[1].unitIds).toEqual(lunaPreview.draft.event_chains[1].source_item_ids);
        expect(eventFragments[0].unitIds.map((id) => tree.units[id].label)).toContain('remis_crisis.1.desc_text');
    });

    it('keeps concrete events deliverable and archive narratives outside event delivery', () => {
        const rawTree = contextResearchPreviewToArchiveTree(lunaPreview);
        const tree = normalizeArchiveTree(rawTree);
        const eventSourceId = lunaPreview.draft.event_chains[0].source_item_ids[0];
        const archiveSourceId = lunaPreview.draft.archive_narratives[0].source_item_ids[0];
        const descSource = lunaPreview.source_items.find((item) => item.key === 'remis_crisis.1.desc');
        const descTextSource = lunaPreview.source_items.find((item) => item.key === 'remis_crisis.1.desc_text');

        expect(buildNarrativeUnitPreview(tree, eventSourceId).hasEventContext).toBe(true);
        expect(buildNarrativeUnitPreview(tree, archiveSourceId).hasEventContext).toBe(false);
        expect(tree.units[archiveSourceId]).toMatchObject({ route: 'no_context' });
        expect(tree.archiveNarrativeIds.every((id) => (
            tree.fragments[id].route === 'no_context'
                && tree.fragments[id].metadata.delivery_target === false
        ))).toBe(true);
        expect(tree.referenceAssets.every((asset) => asset.metadata.receives_event_context === false)).toBe(true);
        expect(tree.units[descSource.source_item_id].sourceRef).toBe(`${descSource.path}::${descSource.key}`);
        expect(tree.units[descTextSource.source_item_id].sourceRef).toBe(`${descTextSource.path}::${descTextSource.key}`);
        expect(rawTree.entity_evidence.some((evidence) => (
            evidence.entity_id === 'entity_remis'
                && evidence.source_ref.endsWith('::remis_crisis.1.desc')
        ))).toBe(true);
        expect(tree.fragments).not.toHaveProperty('fragment-unresolved_root_capital_name');
    });

    it('renders repeated chain identities as ordered steps inside one event-chain group', () => {
        const fixture = {
            project: { project_id: 'chain-test', name: 'Chain test' },
            release: { release_id: 'preview-1' },
            source_items: [
                { source_item_id: 'source-1', key: 'event.1.desc', text: 'First.' },
                { source_item_id: 'source-2', key: 'event.2.desc', text: 'Second.' },
            ],
            draft: {
                event_chains: [
                    {
                        chain_id: 'shared-chain', sequence: 1, event: 'First step.',
                        source_item_ids: ['source-1'], evidence: [],
                    },
                    {
                        chain_id: 'shared-chain', sequence: 2, event: 'Second step.',
                        source_item_ids: ['source-2'], evidence: [],
                    },
                ],
            },
        };

        const tree = normalizeArchiveTree(contextResearchPreviewToArchiveTree(fixture));

        expect(tree.groups).toHaveLength(1);
        expect(tree.groups[0].fragmentIds).toEqual([
            'fragment-shared-chain-1', 'fragment-shared-chain-2',
        ]);
    });

    it('projects research entities without promoting static reference assets', () => {
        const fixture = {
            project: { project_id: 'entity-test', name: 'Entity test' },
            release: { release_id: 'preview-entity' },
            source_items: [{
                source_item_id: 'source-remis', path: 'events/demo.yml',
                key: 'demo.1.desc', text: 'Empress Remis addresses the senate.',
            }],
            draft: {
                entities: [{
                    entity_id: 'remis', name: 'Remis', entity_type: 'person',
                    importance: 'primary', summary: '银河共和国最高执政者。',
                    frequency_grade: 'B', mention_count: 7,
                    local_unit_ids: ['unit_0', 'unit_1'], local_unit_coverage: 2,
                    source_files: ['events/demo.yml'], file_spread: 1,
                    event_chain_ids: ['chain-remis'], event_participation_count: 1,
                    source_item_ids: ['source-remis'],
                    evidence: [{ source_item_ids: ['source-remis'], snippet: 'Empress Remis' }],
                }],
                reference_assets: [{
                    asset_id: 'button-label', name: '确认按钮', description: '静态界面文本。',
                    source_item_ids: ['source-remis'], evidence: [],
                }],
            },
        };

        const rawTree = contextResearchPreviewToArchiveTree(fixture);

        expect(rawTree.candidates).toEqual([expect.objectContaining({
            candidate_id: 'remis', canonical_display_name: 'Remis', tier: 'B',
            mention_count: 7, local_unit_coverage: 2, semantic_importance: 'primary',
            file_spread: 1, event_participation_count: 1,
        })]);
        expect(rawTree.candidates).not.toEqual(expect.arrayContaining([
            expect.objectContaining({ candidate_id: 'button-label' }),
        ]));
        expect(rawTree.entity_evidence[0]).toMatchObject({
            entity_id: 'remis', source_ref: 'events/demo.yml::demo.1.desc',
        });
    });
});

import { describe, expect, it } from 'vitest';

import {
    ANALYSIS_SCOPES,
    buildAnalysisPayload,
    buildTerminologyIndex,
    getCandidateGovernanceGroups,
    getArchiveEntries,
    getTraceabilityRows,
    normalizeAnalysisStatus,
} from './modArchiveModel';

describe('Mod Archive contracts', () => {
    it('builds the terms-only payload without inventing an upstream version', () => {
        expect(buildAnalysisPayload({
            selectedProject: 'project-1',
            apiProvider: 'local',
            modelName: 'model-1',
            targetLang: 'zh-CN',
            descriptionLanguage: 'zh-CN',
            selectedFiles: [],
            analysisScope: ANALYSIS_SCOPES.TERMS_ONLY,
            upstreamVersion: '   ',
            concurrencyLimit: 'auto',
        })).toEqual({
            project_id: 'project-1',
            api_provider: 'local',
            model_name: 'model-1',
            target_lang: 'zh-CN',
            review_language: 'zh-CN',
            description_language: 'zh-CN',
            file_paths: null,
            analysis_scope: 'terms_only',
        });
    });

    it('keeps full archive scope and the optional upstream version in the request', () => {
        const payload = buildAnalysisPayload({
            selectedProject: 'project-1',
            apiProvider: 'local',
            modelName: null,
            targetLang: 'en',
            descriptionLanguage: 'en',
            selectedFiles: ['common/characters.txt'],
            analysisScope: ANALYSIS_SCOPES.NARRATIVE_CONTEXT,
            upstreamVersion: '  1.2.0  ',
            concurrencyLimit: '5',
        });

        expect(payload.analysis_scope).toBe('narrative_context');
        expect(payload.upstream_version).toBe('1.2.0');
        expect(payload.file_paths).toEqual(['common/characters.txt']);
        expect(payload.concurrency_limit).toBe(5);
    });

    it('normalizes task progress while retaining task and release identity', () => {
        expect(normalizeAnalysisStatus({
            status: 'processing',
            task_id: 'task-7',
            analysis_scope: 'narrative_context',
            progress: { current: 2, total: 5, current_file: 'events.yml', stage_code: 'extracting' },
            summary: { new_terms: 3 },
            source_snapshot_hash: 'snapshot-7',
            context_release_id: 'release-7',
        })).toMatchObject({
            status: 'running',
            taskId: 'task-7',
            analysisScope: 'narrative_context',
            processedFiles: 2,
            totalFiles: 5,
            stageCode: 'extracting',
            sourceSnapshotHash: 'snapshot-7',
            contextReleaseId: 'release-7',
        });
    });

    it('prefers observable batch progress and preserves the resumable run configuration', () => {
        expect(normalizeAnalysisStatus({
            status: 'running',
            current_batch: 9,
            total_batches: 18,
            source_items: 275,
            checkpoint: {
                stage: 'extracting',
                resume_supported: true,
                metadata: {
                    configuration: {
                        provider: 'lm_studio',
                        model: 'gemma-4-31b',
                        target_lang: 'zh-CN',
                        description_language: 'zh-CN',
                        analysis_run_id: 'run-7',
                        concurrency_limit: 5,
                        effective_concurrency: 5,
                    },
                },
            },
        })).toMatchObject({
            currentBatch: 9,
            totalBatches: 18,
            sourceItems: 275,
            stageCode: 'extracting',
            provider: 'lm_studio',
            model: 'gemma-4-31b',
            descriptionLanguage: 'zh-CN',
            concurrencyLimit: 5,
            effectiveConcurrency: 5,
            resumeSupported: true,
        });
    });

    it('keeps overall workflow percent separate from current-stage batches', () => {
        expect(normalizeAnalysisStatus({
            status: 'running',
            current_batch: 6,
            total_batches: 6,
            progress: { current_batch: 6, total_batches: 6, percent: 25 },
        })).toMatchObject({
            currentBatch: 6,
            totalBatches: 6,
            overallPercent: 25,
        });
    });

    it('keeps effective overrides and provenance labels available to presentation', () => {
        const effective = {
            effective_context: {
                'project:summary': { summary: 'A project' },
                'entity:republic': { summary: 'A state', preferred_name: '共和国' },
                'event:war': { summary: 'A conflict' },
            },
            human_overrides: {
                'entity:republic': { preferred_name: '共和国（人工确认）' },
            },
        };
        expect(getArchiveEntries(effective)).toEqual(expect.arrayContaining([
            expect.objectContaining({ kind: 'project', label: 'summary' }),
            expect.objectContaining({ kind: 'entity', override: { preferred_name: '共和国（人工确认）' } }),
            expect.objectContaining({ kind: 'event', label: 'war' }),
        ]));
        expect(getTraceabilityRows([{
            aggregate: { aggregate_key: 'entity:republic', aggregate_type: 'entity' },
            contributions: [{
                contribution: { contribution_type: 'fact', provenance: 'script_derived' },
                source_item: { source_ref: 'common/characters.txt::1:republic', content: 'The Republic' },
            }],
        }])).toEqual([expect.objectContaining({
            aggregateKey: 'entity:republic',
            provenance: 'script_derived',
            sourceRef: 'common/characters.txt::1:republic',
        })]);
    });

    it('groups governed candidates by tier while preserving their actual kinds', () => {
        const rows = getTraceabilityRows([
            {
                aggregate: {
                    aggregate_key: 'entity:signal',
                    aggregate_type: 'entity',
                    canonical_display_name: 'Signal',
                    normalized_match_key: 'signal',
                    aliases: ['Signal'],
                    candidate_kind: 'entity',
                    tier: 'A',
                },
                contributions: [{ source_item: { source_ref: 'source::1' } }],
            },
            {
                aggregate: {
                    aggregate_key: 'entity:term',
                    aggregate_type: 'entity',
                    canonical_display_name: 'Admiralty',
                    normalized_match_key: 'admiralty',
                    aliases: ['Admiralty'],
                    candidate_kind: 'glossary_term',
                    tier: 'secondary',
                },
                contributions: [{ source_item: { source_ref: 'source::2' } }],
            },
            {
                aggregate: {
                    aggregate_key: 'entity:concept',
                    aggregate_type: 'entity',
                    canonical_display_name: 'Background concept',
                    normalized_match_key: 'background concept',
                    aliases: ['Background concept'],
                    candidate_kind: 'incidental_concept',
                    tier: 'core',
                },
                contributions: [{ source_item: { source_ref: 'source::3' } }],
            },
        ]);

        const groups = getCandidateGovernanceGroups(rows);
        expect(groups.core).toEqual([
            expect.objectContaining({ candidateKind: 'entity', tier: 'core' }),
            expect.objectContaining({ candidateKind: 'incidental_concept', tier: 'core' }),
        ]);
        expect(groups.secondary).toEqual([
            expect.objectContaining({ candidateKind: 'glossary_term', tier: 'secondary' }),
        ]);
        expect(groups.incidental).toEqual([]);
    });

    it('leaves old traceability records without candidate policy fields unchanged', () => {
        const rows = getTraceabilityRows([{
            aggregate: { aggregate_key: 'entity:legacy', aggregate_type: 'entity' },
            contributions: [{ source_item: { source_ref: 'legacy::1' } }],
        }]);

        expect(rows[0].candidatePolicy).toBeNull();
        expect(getCandidateGovernanceGroups(rows)).toEqual({ core: [], secondary: [], incidental: [] });
    });

    it('decorates archive entities with approved terms before pending suggestions', () => {
        const terminology = buildTerminologyIndex({
            targetLanguage: 'zh-CN',
            glossaryEntries: [{
                source: 'Galactic Republic',
                translations: { 'zh-CN': '银河共和国' },
                metadata: { source_lang: 'en', target_lang: 'zh-CN' },
            }],
            candidates: [
                { original: 'Empress Remis', suggestion: '瑞米斯女皇', status: 'pending' },
                { original: 'Galactic Republic', suggestion: '共和国候选', status: 'pending' },
                { original: 'Rejected Term', suggestion: '不应显示', status: 'rejected' },
            ],
        });
        const entries = getArchiveEntries({
            effective_context: {
                'entity:empress remis': { summary: 'A ruler' },
                'entity:galactic republic': { summary: 'A state' },
            },
        }, terminology);

        expect(entries).toEqual(expect.arrayContaining([
            expect.objectContaining({
                label: 'empress remis',
                termReference: { translation: '瑞米斯女皇', status: 'suggested' },
            }),
            expect.objectContaining({
                label: 'galactic republic',
                termReference: { translation: '银河共和国', status: 'approved' },
            }),
        ]));
        expect(terminology['rejected term']).toBeUndefined();
    });

    it('sorts archive entities by governed tier and then alphabetically', () => {
        const entries = getArchiveEntries({
            effective_context: {
                'entity:zeta': { summary: 'Z' },
                'entity:beta': { summary: 'B' },
                'entity:alpha': { summary: 'A' },
            },
            aggregate_metadata: {
                'entity:zeta': { tier: 'secondary', candidate_kind: 'entity' },
                'entity:beta': { tier: 'core', candidate_kind: 'entity' },
                'entity:alpha': { tier: 'core', candidate_kind: 'entity' },
            },
        });

        expect(entries.map((entry) => entry.label)).toEqual(['alpha', 'beta', 'zeta']);
        expect(entries[0].metadata.tier).toBe('core');
    });
});

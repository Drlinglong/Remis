import { describe, expect, it } from 'vitest';

import {
    ANALYSIS_SCOPES,
    buildAnalysisPayload,
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
            reviewLanguage: 'zh-CN',
            selectedFiles: [],
            analysisScope: ANALYSIS_SCOPES.TERMS_ONLY,
            upstreamVersion: '   ',
        })).toEqual({
            project_id: 'project-1',
            api_provider: 'local',
            model_name: 'model-1',
            target_lang: 'zh-CN',
            review_language: 'zh-CN',
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
            reviewLanguage: 'en',
            selectedFiles: ['common/characters.txt'],
            analysisScope: ANALYSIS_SCOPES.NARRATIVE_CONTEXT,
            upstreamVersion: '  1.2.0  ',
        });

        expect(payload.analysis_scope).toBe('narrative_context');
        expect(payload.upstream_version).toBe('1.2.0');
        expect(payload.file_paths).toEqual(['common/characters.txt']);
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
});

export const ANALYSIS_SCOPES = Object.freeze({
    TERMS_ONLY: 'terms_only',
    NARRATIVE_CONTEXT: 'narrative_context',
});

const STATUS_DEFAULTS = Object.freeze({
    idle: { stage: 'idle', result: 'idle', nextStep: 'choose_project' },
    queued: { stage: 'queued', result: 'queued', nextStep: 'wait' },
    starting: { stage: 'starting', result: 'starting', nextStep: 'wait' },
    running: { stage: 'running', result: 'running', nextStep: 'wait' },
    completed: { stage: 'completed', result: 'completed', nextStep: 'review' },
    failed: { stage: 'failed', result: 'failed', nextStep: 'diagnose' },
});

const asObject = (value) => (
    value && typeof value === 'object' && !Array.isArray(value) ? value : {}
);

const firstValue = (...values) => values.find((value) => value !== undefined && value !== null && value !== '');

export const buildAnalysisPayload = ({
    selectedProject,
    apiProvider,
    modelName,
    targetLang,
    reviewLanguage,
    selectedFiles,
    analysisScope,
    upstreamVersion,
}) => {
    const payload = {
        project_id: selectedProject,
        api_provider: apiProvider,
        model_name: modelName || null,
        target_lang: targetLang,
        review_language: reviewLanguage,
        file_paths: selectedFiles?.length > 0 ? selectedFiles : null,
        analysis_scope: analysisScope || ANALYSIS_SCOPES.TERMS_ONLY,
    };
    const normalizedUpstreamVersion = typeof upstreamVersion === 'string'
        ? upstreamVersion.trim()
        : '';
    if (normalizedUpstreamVersion) payload.upstream_version = normalizedUpstreamVersion;
    return payload;
};

export const normalizeAnalysisStatus = (rawStatus = {}) => {
    const progress = asObject(rawStatus.progress);
    const summary = asObject(rawStatus.summary);
    const result = asObject(rawStatus.result);
    const rawValue = rawStatus.status || 'idle';
    const status = rawValue === 'processing' ? 'running' : rawValue;
    const defaults = STATUS_DEFAULTS[status] || STATUS_DEFAULTS.idle;
    const workflowContext = asObject(rawStatus.workflow_context);

    return {
        status,
        taskId: firstValue(rawStatus.task_id, rawStatus.taskId, rawStatus.id, result.task_id),
        analysisScope: firstValue(
            rawStatus.analysis_scope,
            summary.analysis_scope,
            workflowContext.analysis_scope,
            ANALYSIS_SCOPES.TERMS_ONLY,
        ),
        processedFiles: firstValue(
            rawStatus.processed_files,
            progress.current,
            progress.current_files,
            0,
        ),
        totalFiles: firstValue(rawStatus.total_files, progress.total, progress.total_files, 0),
        newTerms: firstValue(rawStatus.new_terms, summary.new_terms, result.new_terms, 0),
        duplicateTerms: firstValue(
            rawStatus.duplicate_terms,
            summary.duplicate_terms,
            result.duplicate_terms,
            0,
        ),
        currentFile: firstValue(rawStatus.current_file, progress.current_file, null),
        error: firstValue(rawStatus.error, summary.error, result.error, null),
        sourceSnapshotHash: firstValue(
            rawStatus.source_snapshot_hash,
            result.source_snapshot_hash,
            null,
        ),
        contextReleaseId: firstValue(
            rawStatus.context_release_id,
            result.context_release_id,
            null,
        ),
        stageCode: firstValue(
            rawStatus.stage_code,
            rawStatus.stage,
            progress.stage_code,
            progress.stage,
            defaults.stage,
        ),
        resultCode: firstValue(
            rawStatus.result_code,
            result.result_code,
            summary.result_code,
            defaults.result,
        ),
        nextStepCode: firstValue(
            rawStatus.next_step_code,
            rawStatus.nextStepCode,
            rawStatus.attention_reason_code,
            defaults.nextStep,
        ),
    };
};

export const getStatusTone = (status) => {
    if (status === 'failed') return 'error';
    if (status === 'completed') return 'success';
    if (status === 'idle') return 'muted';
    return 'active';
};

export const isReleaseStale = (release, analysisStatus) => {
    const releaseHash = release?.metadata?.source_snapshot_hash;
    const currentHash = analysisStatus?.sourceSnapshotHash;
    return Boolean(releaseHash && currentHash && releaseHash !== currentHash);
};

const getEntryKind = (key) => {
    if (key === 'project:summary' || key === 'project') return 'project';
    if (key.startsWith('event:') || key.startsWith('event/')) return 'event';
    return 'entity';
};

const getEntryLabel = (key) => key.replace(/^(project|entity|event)[:/]/, '');

export const getArchiveEntries = (effectiveResponse) => {
    const effectiveContext = asObject(effectiveResponse?.effective_context);
    const humanOverrides = asObject(effectiveResponse?.human_overrides);
    const keys = new Set([...Object.keys(effectiveContext), ...Object.keys(humanOverrides)]);
    return Array.from(keys)
        .map((key) => ({
            key,
            kind: getEntryKind(key),
            label: getEntryLabel(key),
            value: asObject(effectiveContext[key] || humanOverrides[key]),
            override: humanOverrides[key] || humanOverrides[getEntryLabel(key)] || null,
        }))
        .sort((left, right) => {
            const order = { project: 0, entity: 1, event: 2 };
            return (order[left.kind] - order[right.kind]) || left.label.localeCompare(right.label);
        });
};

export const getArchiveCounts = (effectiveResponse) => {
    const entries = getArchiveEntries(effectiveResponse);
    return entries.reduce((counts, entry) => ({
        ...counts,
        [entry.kind]: counts[entry.kind] + 1,
    }), { project: 0, entity: 0, event: 0 });
};

export const getTraceabilityRows = (traceability = []) => (
    (Array.isArray(traceability) ? traceability : []).flatMap((record) => {
        const aggregate = asObject(record?.aggregate);
        return (Array.isArray(record?.contributions) ? record.contributions : []).map((item) => {
            const contribution = asObject(item?.contribution);
            const source = asObject(item?.source_item);
            return {
                aggregateKey: aggregate.aggregate_key || '',
                aggregateType: aggregate.aggregate_type || 'entity',
                contributionType: contribution.contribution_type || 'mention',
                provenance: contribution.provenance || 'text_inferred',
                sourceRef: source.source_ref || source.source_item_id || '',
                sourceContent: source.content || '',
            };
        });
    })
);

export const getErrorMessage = (error, fallback = '') => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (typeof error?.message === 'string') return error.message;
    return fallback;
};

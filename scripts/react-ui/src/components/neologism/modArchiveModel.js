export const ANALYSIS_SCOPES = Object.freeze({
    TERMS_ONLY: 'terms_only',
    NARRATIVE_CONTEXT: 'narrative_context',
});

export const ARCHIVE_OVERRIDE_FIELD_KEYS = Object.freeze([
    'summary',
    'preferred_name',
    'entity_type',
    'event_membership',
    'relationship_correction',
]);

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
    descriptionLanguage,
    selectedFiles,
    analysisScope,
    upstreamVersion,
}) => {
    const payload = {
        project_id: selectedProject,
        api_provider: apiProvider,
        model_name: modelName || null,
        target_lang: targetLang,
        review_language: descriptionLanguage,
        description_language: descriptionLanguage,
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
    const checkpoint = asObject(rawStatus.checkpoint);
    const checkpointMetadata = asObject(checkpoint.metadata);
    const checkpointConfiguration = asObject(checkpointMetadata.configuration);
    const checkpointStages = asObject(checkpointMetadata.stages);
    const checkpointStage = asObject(checkpointStages[checkpoint.stage]);

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
        sourceItems: firstValue(rawStatus.source_items, checkpointMetadata.source_items, 0),
        currentBatch: firstValue(
            rawStatus.current_batch,
            checkpointStage.successful_batch_ids?.length,
            progress.current_batch,
            0,
        ),
        totalBatches: firstValue(
            rawStatus.total_batches,
            checkpointStage.total_batches,
            checkpointMetadata.total_batches,
            progress.total_batches,
            0,
        ),
        successfulBatches: firstValue(rawStatus.successful_batches, 0),
        failedBatches: firstValue(rawStatus.failed_batches, 0),
        overallPercent: Number(firstValue(rawStatus.overall_percent, progress.percent, 0)),
        conflictReviewCount: firstValue(rawStatus.conflict_review_count, 0),
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
            checkpoint.stage,
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
        provider: firstValue(rawStatus.provider, workflowContext.provider, checkpointConfiguration.provider, null),
        model: firstValue(rawStatus.model, workflowContext.model, checkpointConfiguration.model, null),
        targetLang: firstValue(
            rawStatus.target_lang,
            workflowContext.target_lang,
            checkpointConfiguration.target_lang,
            null,
        ),
        descriptionLanguage: firstValue(
            rawStatus.description_language,
            workflowContext.description_language,
            checkpointConfiguration.description_language,
            null,
        ),
        analysisRunId: firstValue(
            rawStatus.analysis_run_id,
            workflowContext.analysis_run_id,
            checkpointConfiguration.analysis_run_id,
            null,
        ),
        resumeSupported: Boolean(checkpoint.resume_supported),
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

const normalizeTerm = (value) => String(value || '').normalize('NFKC').trim().toLocaleLowerCase();

const glossaryTranslation = (entry, targetLanguage) => {
    const translations = asObject(entry?.translations);
    const configuredTarget = entry?.metadata?.target_lang || entry?.raw_metadata?.target_lang;
    return firstValue(
        translations[targetLanguage],
        translations[configuredTarget],
        Object.entries(translations).find(([language, value]) => (
            language !== entry?.metadata?.source_lang && Boolean(value)
        ))?.[1],
    );
};

export const buildTerminologyIndex = ({
    glossaryEntries = [],
    candidates = [],
    targetLanguage,
} = {}) => {
    const index = {};
    glossaryEntries.forEach((entry) => {
        const source = entry?.source || entry?.metadata?.source_text || entry?.raw_metadata?.source_text;
        const translation = glossaryTranslation(entry, targetLanguage);
        if (!source || !translation || normalizeTerm(source) === normalizeTerm(translation)) return;
        index[normalizeTerm(source)] = { translation, status: 'approved' };
    });
    candidates.forEach((candidate) => {
        const source = candidate?.original;
        const translation = candidate?.suggestion;
        const key = normalizeTerm(source);
        if (!key || !translation || index[key] || candidate?.status !== 'pending') return;
        index[key] = { translation, status: 'suggested' };
    });
    return index;
};

export const getArchiveEntries = (effectiveResponse, terminologyIndex = {}) => {
    const effectiveContext = asObject(effectiveResponse?.effective_context);
    const humanOverrides = asObject(effectiveResponse?.human_overrides);
    const keys = new Set([...Object.keys(effectiveContext), ...Object.keys(humanOverrides)]);
    return Array.from(keys)
        .map((key) => {
            const label = getEntryLabel(key);
            return {
                key,
                kind: getEntryKind(key),
                label,
                termReference: terminologyIndex[normalizeTerm(label)] || null,
                value: asObject(effectiveContext[key] || humanOverrides[key]),
                override: humanOverrides[key] || humanOverrides[label] || null,
            };
        })
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

export const getContextErrorCode = (error) => {
    const detail = error?.response?.data?.detail;
    return typeof detail?.code === 'string' ? detail.code : 'context_request_failed';
};

export const getDraftOverride = (draft, contextKey) => (
    (Array.isArray(draft?.overrides) ? draft.overrides : [])
        .find((override) => override?.target_key === contextKey) || null
);

const asEditorText = (value) => {
    if (value === undefined || value === null) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object' && typeof value.summary === 'string') return value.summary;
    return '';
};

export const getEditorValues = (entry, draftOverride) => {
    const generatedValue = asObject(entry?.value);
    const overrideValue = asObject(draftOverride?.value);
    const combined = { ...generatedValue, ...overrideValue };
    return Object.fromEntries(
        ARCHIVE_OVERRIDE_FIELD_KEYS.map((key) => [key, asEditorText(combined[key])]),
    );
};

export const buildOverrideDelta = (values, initialValues) => Object.fromEntries(
    ARCHIVE_OVERRIDE_FIELD_KEYS.flatMap((key) => {
        const value = typeof values?.[key] === 'string' ? values[key].trim() : '';
        const initial = typeof initialValues?.[key] === 'string'
            ? initialValues[key].trim()
            : '';
        return value && value !== initial ? [[key, value]] : [];
    }),
);

export const getErrorMessage = (error, fallback = '') => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (typeof error?.message === 'string') return error.message;
    return fallback;
};

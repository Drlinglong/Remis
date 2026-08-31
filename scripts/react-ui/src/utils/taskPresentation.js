import { formatLocalizedDateTime } from './localizedDateTime';

const TERMINAL_STATUSES = new Set(['completed', 'partial_failed', 'failed', 'interrupted', 'cancelled']);
const ARCHIVE_STAGE_CODES = new Set([
  'idle', 'queued', 'starting', 'running', 'extracting', 'reviewing',
  'aggregating', 'synthesizing', 'publishing', 'completed', 'failed',
]);
const PROVIDER_FAILURE_KEYS = {
  provider_invalid_model: 'invalid_model',
  provider_authentication_failed: 'authentication_failed',
  provider_forbidden: 'forbidden',
  provider_invalid_request: 'invalid_request',
};

const numeric = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const formatTaskTimestamp = (value, locale) => {
  if (!value) return '--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return formatLocalizedDateTime(parsed, locale);
};

export const getTaskStageLabel = (task, t) => {
  if (!task) return '';
  const statusLabel = t(`task_center.status.${task.status}`, { defaultValue: task.status });
  if (TERMINAL_STATUSES.has(task.status)) return statusLabel;

  const raw = String(task.stage || task.message || '').trim();
  const stageCode = task.stage_code || task.progress?.stage_code;
  if (['neologism_mining', 'context_archive_analysis'].includes(task.kind) && ARCHIVE_STAGE_CODES.has(stageCode)) {
    return t(`mod_archive.status.stage.${stageCode}`);
  }
  if (task.kind !== 'incremental_translation') return raw || statusLabel;

  const stageCodeKeys = {
    initializing: 'preparing',
    scanning_source: 'scanning',
    loading_archive: 'comparing',
    comparing_entries: 'comparing',
    translating_content: 'translating',
    finishing: 'validating',
    completed: 'completed',
    failed: 'failed',
  };
  if (stageCodeKeys[stageCode]) {
    return ['completed', 'failed'].includes(stageCode)
      ? statusLabel
      : t(`task_presentation.incremental.${stageCodeKeys[stageCode]}`);
  }

  // Compatibility for task records created before stage_code was persisted.
  if (/queue|initializ/i.test(raw)) return t('task_presentation.incremental.preparing');
  if (/scan/i.test(raw)) return t('task_presentation.incremental.scanning');
  if (/archive|compar/i.test(raw)) return t('task_presentation.incremental.comparing');
  if (/translat/i.test(raw)) return t('task_presentation.incremental.translating');
  if (/proofread|format|workshop/i.test(raw)) return t('task_presentation.incremental.validating');
  return statusLabel;
};

export const getTaskResultSummary = (task, t) => {
  if (!task) return '';
  const metadata = task.result?.metadata || {};
  const summaryCode = metadata.summary_code;

  if (summaryCode === 'incremental_translation_completed') {
    return t('task_presentation.result.incremental_completed', {
      count: numeric(metadata.processed_file_count),
    });
  }
  if (summaryCode === 'format_scan_completed') {
    return t('task_presentation.result.format_scan_completed', {
      count: numeric(metadata.issue_count),
    });
  }
  if (['agent_workshop', 'agent_workshop_batch'].includes(task.kind)) {
    const results = Array.isArray(metadata.results) ? metadata.results : [];
    const fixed = numeric(
      metadata.success_count ?? task.summary?.successCount,
      results.filter((item) => item?.status === 'SUCCESS').length,
    );
    const remaining = numeric(
      metadata.failed_count ?? task.summary?.failedCount,
      results.filter((item) => item?.status !== 'SUCCESS').length,
    );
    if (fixed || remaining || results.length > 0) {
      return remaining > 0
        ? t('task_presentation.result.format_repair_partial', { fixed, remaining })
        : t('task_presentation.result.format_repair_completed', { fixed });
    }
  }

  const raw = String(task.result?.summary || '').trim();
  const incrementalMatch = raw.match(/^(\d+) file\(s\) processed;\s*(\d+) runtime warning\(s\)\.?$/i);
  if (incrementalMatch) {
    return t('task_presentation.result.incremental_completed_with_warnings', {
      files: Number(incrementalMatch[1]),
      warnings: Number(incrementalMatch[2]),
    });
  }
  return raw;
};

export const getTaskNextStep = (task, t) => {
  if (!task) return '';
  if (PROVIDER_FAILURE_KEYS[task.attention_reason_code]) {
    return t(`task_presentation.provider_failure.${PROVIDER_FAILURE_KEYS[task.attention_reason_code]}.action`);
  }
  if (task.attention_reason_code === 'incremental_translation_internal_error') {
    return t('task_presentation.next_step.internal_error');
  }
  if (task.attention_reason_code === 'incremental_translation_failed_review_diagnostics') {
    return t('task_presentation.next_step.review_failure');
  }
  if (task.status === 'failed' || task.status === 'interrupted') {
    return t('task_presentation.next_step.review_failure');
  }
  if (task.kind === 'incremental_translation' && task.status === 'completed') {
    return t('task_presentation.next_step.proofread');
  }
  if (task.kind === 'agent_workshop_scan' && task.status === 'completed') {
    return numeric(task.result?.metadata?.issue_count) > 0
      ? t('task_presentation.next_step.review_format_issues')
      : t('task_presentation.next_step.no_action_required');
  }
  if (['agent_workshop', 'agent_workshop_batch'].includes(task.kind) && task.status === 'partial_failed') {
    return t('task_presentation.next_step.review_format_failures');
  }
  if (task.status === 'completed') return t('task_presentation.next_step.completed');
  return t('task_presentation.next_step.wait');
};

export const getTaskFailurePresentation = (task, t) => {
  const key = PROVIDER_FAILURE_KEYS[task?.attention_reason_code];
  if (!key) return null;
  return {
    title: t(`task_presentation.provider_failure.${key}.title`),
    message: getTaskNextStep(task, t),
  };
};

export const getTaskEventPresentation = (event, task, t) => {
  const message = String(event?.message || '').trim();
  if (task?.kind !== 'incremental_translation') {
    return { message, technical: event?.audience === 'diagnostic' };
  }

  if (/^Queuing incremental update/i.test(message)) {
    return { message: t('task_presentation.event.incremental_queued'), technical: false };
  }
  const scanned = message.match(/^Scanned (\d+) files?\.?$/i);
  if (scanned) {
    return {
      message: t('task_presentation.event.files_scanned', { count: Number(scanned[1]) }),
      technical: false,
    };
  }
  const translating = message.match(/^Translating\s+([^:]+):\s*(\d+)\/(\d+)\s+batches?/i);
  if (translating) {
    return {
      message: t('task_presentation.event.translating_batches', {
        language: translating[1].toUpperCase(),
        current: Number(translating[2]),
        total: Number(translating[3]),
      }),
      technical: false,
    };
  }
  if (/^Incremental (translation|update) completed/i.test(message)) {
    return { message: t('task_presentation.event.incremental_completed'), technical: false };
  }
  if (/Smart Workshop: Proofreading and fixing format issues/i.test(message)) {
    return { message: t('task_presentation.event.format_validation'), technical: false };
  }
  if (/^Pre-fetching archive|^Comparing /i.test(message)) {
    return { message: t('task_presentation.event.comparing_archive'), technical: false };
  }
  if (/No models loaded/i.test(message)) {
    return { message: t('glossary_health_no_model_loaded'), technical: true };
  }
  return { message, technical: true };
};

export const sortTaskEventsNewestFirst = (events = []) => (
  [...events].sort((left, right) => {
    const leftTime = new Date(left?.timestamp || 0).getTime();
    const rightTime = new Date(right?.timestamp || 0).getTime();
    if (rightTime !== leftTime) return rightTime - leftTime;
    return String(right?.event_id || '').localeCompare(String(left?.event_id || ''));
  })
);

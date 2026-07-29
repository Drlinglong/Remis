import { describe, expect, it } from 'vitest';

import {
  getTaskEventPresentation,
  getTaskNextStep,
  getTaskResultSummary,
  getTaskStageLabel,
  sortTaskEventsNewestFirst,
} from './taskPresentation';

const t = (key, params = {}) => `${key}:${JSON.stringify(params)}`;

describe('task presentation', () => {
  it('never presents a failed incremental task as translating', () => {
    const label = getTaskStageLabel({
      kind: 'incremental_translation',
      status: 'failed',
      stage: 'Translating',
    }, t);

    expect(label).toContain('task_center.status.failed');
    expect(label).not.toMatch(/Translating/i);
  });

  it('prefers structured stage and recovery codes over English backend copy', () => {
    expect(getTaskStageLabel({
      kind: 'incremental_translation',
      status: 'running',
      stage: 'Translating',
      stage_code: 'comparing_entries',
    }, t)).toContain('task_presentation.incremental.comparing');

    const failedTask = {
      kind: 'incremental_translation',
      status: 'failed',
      stage: 'Failed',
      stage_code: 'failed',
      attention_reason: 'Return to Incremental Translation and retry.',
      attention_reason_code: 'incremental_translation_internal_error',
    };
    expect(getTaskStageLabel(failedTask, t)).toContain('task_center.status.failed');
    expect(getTaskNextStep(failedTask, t)).toContain('task_presentation.next_step.internal_error');
    expect(getTaskNextStep(failedTask, t)).not.toContain('Return to Incremental');
  });

  it('localizes persisted incremental summaries and deterministic format scans', () => {
    expect(getTaskResultSummary({
      result: { summary: '2 file(s) processed; 0 runtime warning(s).' },
    }, t)).toContain('task_presentation.result.incremental_completed_with_warnings');

    expect(getTaskResultSummary({
      result: {
        metadata: {
          summary_code: 'format_scan_completed',
          issue_count: 0,
        },
      },
    }, t)).toContain('"count":0');
  });

  it('maps known incremental events and treats unknown implementation logs as technical', () => {
    expect(getTaskEventPresentation(
      { message: 'Translating en: 2/3 batches' },
      { kind: 'incremental_translation' },
      t,
    )).toEqual(expect.objectContaining({
      technical: false,
      message: expect.stringContaining('task_presentation.event.translating_batches'),
    }));

    expect(getTaskEventPresentation(
      { message: 'internal_provider_payload=opaque' },
      { kind: 'incremental_translation' },
      t,
    )).toEqual({
      message: 'internal_provider_payload=opaque',
      technical: true,
    });

    expect(getTaskEventPresentation(
      { message: "Error code: 400 - No models loaded. Please load a model." },
      { kind: 'incremental_translation' },
      t,
    )).toEqual({
      message: 'glossary_health_no_model_loaded:{}',
      technical: true,
    });
  });

  it('orders newest events first and keeps equal timestamps deterministic', () => {
    const events = sortTaskEventsNewestFirst([
      { event_id: 'a', timestamp: '2026-07-26T10:00:00Z' },
      { event_id: 'c', timestamp: '2026-07-26T10:01:00Z' },
      { event_id: 'b', timestamp: '2026-07-26T10:00:00Z' },
    ]);

    expect(events.map((event) => event.event_id)).toEqual(['c', 'b', 'a']);
  });
});

import { readArrayPayload, readRecordArray, unwrapRecordPayload } from '../utils/workflowPayload';

const strings = (value, name) => {
  const items = readArrayPayload(value, name);
  if (items.some((item) => typeof item !== 'string')) throw new TypeError(`Invalid ${name}: expected strings`);
  return items;
};

export function normalizeArchiveABCases(value) {
  return readRecordArray(value, 'cases').map((item) => ({
    ...item,
    source_entries: readRecordArray(item.source_entries, 'source_entries'),
    story_facts: strings(item.story_facts, 'story_facts'),
    anonymous_outputs: readRecordArray(item.anonymous_outputs, 'anonymous_outputs').map((output) => ({
      ...output, entries: readRecordArray(output.entries, 'output entries'),
    })),
    review: item.review ? { ...item.review, error_tags: strings(item.review.error_tags, 'error_tags') } : null,
    reveal: item.reveal ? {
      ...item.reveal,
      actual_order: strings(item.reveal.actual_order, 'actual_order'),
      llm_evidence: strings(item.reveal.llm_evidence, 'llm_evidence'),
    } : null,
  }));
}

export function normalizeArchiveABBatch(value) {
  const data = unwrapRecordPayload(value, 'Archive A/B');
  if (!Object.hasOwn(data, 'manifests') || !Object.hasOwn(data, 'cases')) {
    throw new TypeError('Invalid Archive A/B response: missing manifests or cases');
  }
  return { ...data, manifests: readRecordArray(data.manifests, 'manifests'),
    cases: normalizeArchiveABCases(data.cases) };
}

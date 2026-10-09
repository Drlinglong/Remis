import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../utils/api';
import service from './archiveABReviewService';

vi.mock('../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe('Archive A/B response boundary', () => {
  beforeEach(() => vi.resetAllMocks());

  it('unwraps batch and nested arrays without losing counts or identities', async () => {
    const item = { case_id: 'case-1', manifest_id: 'run-1',
      source_entries: { items: [{ source_id: 'a', text: '$OWNER$ [Root.GetName]' }] },
      anonymous_outputs: { data: [{ anonymous_label: 'left', entries: null }] } };
    api.get.mockResolvedValue({ data: { data: { total_count: 7, reviewed_count: 2,
      manifests: { items: [{ manifest_id: 'run-1' }] }, cases: { data: [item] } } } });
    const batch = await service.loadCases();
    expect(batch.total_count).toBe(7);
    expect(batch.reviewed_count).toBe(2);
    expect(batch.manifests[0].manifest_id).toBe('run-1');
    expect(batch.cases[0].source_entries[0].text).toBe('$OWNER$ [Root.GetName]');
    expect(batch.cases[0].anonymous_outputs[0].entries).toEqual([]);
  });

  it('allows explicitly empty lists', async () => {
    api.get.mockResolvedValue({ data: { manifests: null, cases: null } });
    expect(await service.loadCases()).toMatchObject({ manifests: [], cases: [] });
  });

  it.each([
    null, {}, { manifests: {}, cases: [] }, { manifests: [], cases: {} }, { manifests: [], cases: [null] },
    { manifests: [], cases: [{ source_entries: {} }] }, { manifests: [], cases: [{ anonymous_outputs: [null] }] },
  ])('rejects malformed input instead of claiming an empty successful batch: %j', async (data) => {
    api.get.mockResolvedValue({ data });
    await expect(service.loadCases()).rejects.toThrow(/Invalid/);
  });

  it('normalizes a saved case and rejects a missing saved case', async () => {
    api.post.mockResolvedValueOnce({ data: { case: { case_id: 'a', source_entries: null } } });
    expect((await service.submitReview({})).case.source_entries).toEqual([]);
    api.post.mockResolvedValueOnce({ data: {} });
    await expect(service.submitReview({})).rejects.toThrow(/Invalid cases/);
  });
});

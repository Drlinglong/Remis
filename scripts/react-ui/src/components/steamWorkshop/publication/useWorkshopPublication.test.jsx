import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { workshopPublicationService as service } from '../../../services/workshopPublicationService';
import { useWorkshopPublication } from './useWorkshopPublication';

vi.mock('../../../services/workshopPublicationService', () => ({
  workshopPublicationService: { options: vi.fn(), history: vi.fn(), plan: vi.fn(), submit: vi.fn(), verify: vi.fn() },
}));

const plan = { plan_id: 'one', fingerprint: 'a'.repeat(64), status: 'preview', allowed_actions: ['approve_publication'] };
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

describe('publication controller approval and request lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    service.options.mockResolvedValue({ outputs: [], runtime: { ready: true } });
    service.history.mockResolvedValue([]);
    service.plan.mockResolvedValue(plan);
    service.submit.mockResolvedValue({ ...plan, status: 'running', allowed_actions: [] });
    service.verify.mockResolvedValue({ ...plan, status: 'resolved', allowed_actions: [] });
  });
  afterEach(() => vi.useRealTimers());

  it('does not submit when generating a preview', async () => {
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({ title: 'Translation' }));
    expect(result.current.preview).toEqual(plan);
    expect(service.submit).not.toHaveBeenCalled();
  });

  it('invalidates the approval identity when form inputs change', async () => {
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({}));
    act(() => result.current.invalidate());
    await act(async () => result.current.submit());
    expect(result.current.preview).toBeNull();
    expect(service.submit).not.toHaveBeenCalled();
  });

  it('ignores an outdated preview response after editing', async () => {
    const request = deferred();
    service.plan.mockReturnValue(request.promise);
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    let pending;
    act(() => { pending = result.current.createPreview({}); });
    act(() => result.current.invalidate());
    await act(async () => { request.resolve(plan); await pending; });
    expect(result.current.preview).toBeNull();
  });

  it('deduplicates rapid clicks and sends the reviewed fingerprint', async () => {
    const request = deferred();
    service.submit.mockReturnValue(request.promise);
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({}));
    let pending;
    act(() => {
      pending = result.current.submit();
      result.current.submit();
    });
    expect(service.submit).toHaveBeenCalledTimes(1);
    expect(service.submit).toHaveBeenCalledWith('workspace', plan);
    await act(async () => { request.resolve({ ...plan, status: 'running', allowed_actions: [] }); await pending; });
    await act(async () => result.current.submit());
    expect(service.submit).toHaveBeenCalledTimes(1);
  });

  it('clears stale approval after a server rejection and shows its reason', async () => {
    service.submit.mockRejectedValue({ response: { data: { detail: { code: 'stale_plan', message: 'Create a fresh preview' } } } });
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({}));
    await act(async () => result.current.submit());
    expect(result.current.preview).toBeNull();
    expect(result.current.error).toBe('Create a fresh preview');
  });

  it('restores running publication history on remount', async () => {
    service.history.mockResolvedValue([{ ...plan, status: 'running' }]);
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await waitFor(() => expect(result.current.history[0]?.status).toBe('running'));
    expect(service.submit).not.toHaveBeenCalled();
  });

  it('does not restore approval when a pre-submit history response arrives last', async () => {
    const oldHistory = deferred();
    const running = { ...plan, status: 'running', allowed_actions: [] };
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({}));
    service.history.mockReturnValueOnce(oldHistory.promise).mockResolvedValue([running]);
    let pending;
    act(() => { pending = result.current.refresh(); });
    await act(async () => result.current.submit());
    await act(async () => { oldHistory.resolve([plan]); await pending; });
    expect(result.current.preview.status).toBe('running');
    expect(result.current.preview.allowed_actions).toEqual([]);
    await act(async () => result.current.submit());
    expect(service.submit).toHaveBeenCalledTimes(1);
  });

  it('shows the submission result immediately while the follow-up history is pending', async () => {
    service.history.mockResolvedValue([plan]);
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({}));
    const followUp = deferred();
    service.history.mockReturnValueOnce(followUp.promise);
    let pending;
    await act(async () => { pending = result.current.submit(); });
    expect(result.current.preview.status).toBe('running');
    await act(async () => { followUp.resolve([{ ...plan, status: 'running', allowed_actions: [] }]); await pending; });
  });

  it.each(['succeeded', 'failed', 'unknown', 'legal_agreement_required', 'resolved'])(
  'keeps %s history when a later refresh returns an older status', async (status) => {
    const terminal = { ...plan, status, allowed_actions: [] };
    service.history.mockResolvedValue([terminal]);
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await waitFor(() => expect(result.current.history).toEqual([terminal]));
    service.history.mockResolvedValue([{ ...plan, status: 'running', allowed_actions: [] }]);
    await act(async () => result.current.refresh());
    expect(result.current.history).toEqual([terminal]);
  });

  it('allows a manually verified unknown outcome to advance to resolved', async () => {
    service.history.mockResolvedValue([{ ...plan, status: 'unknown', allowed_actions: ['verify_remote_outcome'] }]);
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await waitFor(() => expect(result.current.history[0]?.status).toBe('unknown'));
    service.history.mockResolvedValue([{ ...plan, status: 'resolved', allowed_actions: [] }]);
    await act(async () => result.current.refresh());
    expect(result.current.history[0].status).toBe('resolved');
  });

  it('does not overlap polling when history takes longer than the poll interval', async () => {
    const running = { ...plan, status: 'running', allowed_actions: [] };
    service.history.mockResolvedValue([running]);
    vi.useFakeTimers();
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => {});
    expect(result.current.history).toEqual([running]);
    const slow = deferred();
    service.history.mockReturnValueOnce(slow.promise);
    await act(async () => vi.advanceTimersByTime(6000));
    expect(service.history).toHaveBeenCalledTimes(2);
    await act(async () => slow.resolve([running]));
    await act(async () => vi.advanceTimersByTime(2000));
    expect(service.history).toHaveBeenCalledTimes(3);
  });

  it('ignores an older refresh failure after a newer history request succeeds', async () => {
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.refresh());
    let reject;
    service.history.mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
    let pending;
    act(() => { pending = result.current.refresh(); });
    await act(async () => result.current.refresh());
    await act(async () => { reject(new Error('Old request failed')); await pending; });
    expect(result.current.error).toBe('');
  });

  it('shows field-specific schema validation errors instead of a generic 422', async () => {
    service.plan.mockRejectedValue({ message: 'Request failed with status code 422', response: { data: {
      detail: [{ loc: ['body', 'published_file_id'], msg: 'String should match the ID pattern' }],
    } } });
    const { result } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.createPreview({}));
    expect(result.current.error).toBe('published_file_id: String should match the ID pattern');
  });

  it('does not report verification completion or refresh after unmount', async () => {
    const verification = deferred();
    service.verify.mockReturnValueOnce(verification.promise);
    const { result, unmount } = renderHook(() => useWorkshopPublication('workspace'));
    await act(async () => result.current.refresh());
    let pending;
    act(() => { pending = result.current.verify('one', { verified: true, resolution: 'item_absent' }); });
    const requests = service.history.mock.calls.length;
    unmount();
    let completed;
    await act(async () => { verification.resolve({ status: 'resolved' }); completed = await pending; });
    expect(completed).toBe(false);
    expect(service.history).toHaveBeenCalledTimes(requests);
  });
});

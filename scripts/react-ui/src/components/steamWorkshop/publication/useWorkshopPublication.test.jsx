import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { workshopPublicationService as service } from '../../../services/workshopPublicationService';
import { useWorkshopPublication } from './useWorkshopPublication';

vi.mock('../../../services/workshopPublicationService', () => ({
  workshopPublicationService: { options: vi.fn(), history: vi.fn(), plan: vi.fn(), submit: vi.fn() },
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
});

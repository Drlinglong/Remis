import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../utils/api';
import { useCollectionRequestLifecycle } from './useCollectionRequestLifecycle';
import { useCollectionProjectOptions } from './useCollectionProjectOptions';
import { useCollectionExportController } from './useCollectionExportController';

vi.mock('../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};

describe('translation collection controller boundaries', () => {
  beforeEach(() => vi.resetAllMocks());

  it('keeps a reopened session busy when a request from the closed session fails', async () => {
    const old = deferred();
    const current = deferred();
    const { result, rerender } = renderHook(({ opened }) => useCollectionRequestLifecycle(opened), {
      initialProps: { opened: true },
    });
    let oldRun;
    act(() => { oldRun = result.current.run(() => old.promise); });
    rerender({ opened: false });
    rerender({ opened: true });
    let currentRun;
    act(() => { currentRun = result.current.run(() => current.promise); });
    await act(async () => { old.reject(new Error('closed-session error')); await oldRun; });
    expect(result.current.busy).toBe(true);
    expect(result.current.error).toBe('');
    await act(async () => { current.resolve('done'); await currentRun; });
    expect(result.current.busy).toBe(false);
  });

  it('does not let stale project option errors clear a newer selection request or error state', async () => {
    const old = deferred();
    const current = deferred();
    api.get.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const { result } = renderHook(() => {
      const lifecycle = useCollectionRequestLifecycle(true);
      return { ...lifecycle, ...useCollectionProjectOptions(lifecycle) };
    });
    let oldRequest;
    act(() => { oldRequest = result.current.loadProjectOptions('shared'); });
    act(() => result.current.nextSelection());
    let currentRequest;
    act(() => { currentRequest = result.current.loadProjectOptions('shared'); });
    await act(async () => { old.reject(new Error('old output error')); await oldRequest; });
    expect(result.current.optionsLoading.shared).toBe(true);
    expect(result.current.error).toBe('');
    const data = { translation_outputs: [{ language_code: 'en', output_folder_name: 'en-new' }] };
    await act(async () => { current.resolve({ data }); await currentRequest; });
    expect(result.current.projectOptions.shared).toEqual(data);
    expect(result.current.optionsLoading.shared).toBe(false);
    await act(async () => expect(await result.current.loadProjectOptions('shared')).toEqual(data));
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('keeps an invalidated delayed export plan from restoring export authorization', async () => {
    const pending = deferred();
    api.post.mockReturnValueOnce(pending.promise);
    const selected = { collection_id: 'c1' };
    const onSelected = vi.fn();
    const refresh = vi.fn();
    const { result } = renderHook(() => {
      const lifecycle = useCollectionRequestLifecycle(true);
      return useCollectionExportController({ ...lifecycle, selected, draftDirty: false, onSelected, refresh });
    });
    let planning;
    act(() => { planning = result.current.plan(); });
    act(() => result.current.invalidatePreview());
    await act(async () => {
      pending.resolve({ data: { plan_id: 'old-plan', inspection: { can_export: true } } });
      await planning;
    });
    expect(result.current.preview).toBeNull();
    await act(async () => result.current.exportPackage());
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(onSelected).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });
});

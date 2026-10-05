import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../utils/api';
import { useTranslationCollections } from './useTranslationCollections';

vi.mock('../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }));

describe('useTranslationCollections', () => {
  beforeEach(() => vi.resetAllMocks());

  it('loads collection list and reports API failures visibly', async () => {
    api.get.mockResolvedValueOnce({ data: { collections: [{ collection_id: 'c1' }] } });
    const { result } = renderHook(() => useTranslationCollections(true));
    await waitFor(() => expect(result.current.collections).toHaveLength(1));
    api.get.mockRejectedValueOnce(new Error('network down'));
    await act(async () => result.current.refresh());
    expect(result.current.error).toBe('network down');
  });

  it('sends explicit approval only after preview and invalidates the preview after edits', async () => {
    api.get.mockResolvedValue({ data: { collections: [] } });
    api.post.mockResolvedValueOnce({ data: { plan_id: 'p1', inspection: { can_export: true } } });
    const { result } = renderHook(() => useTranslationCollections(true));
    await act(async () => { result.current.setSelected({ collection_id: 'c1' }); });
    await act(async () => result.current.plan());
    expect(result.current.preview.plan_id).toBe('p1');
    act(() => result.current.invalidatePreview());
    expect(result.current.preview).toBeNull();
    api.post.mockResolvedValueOnce({ data: { package_path: '/out.zip' } });
    await act(async () => result.current.exportPackage());
    expect(api.post).not.toHaveBeenCalledWith('/api/translation-collections/c1/export', expect.anything());
  });

  it('sends approved export against the current preview plan', async () => {
    api.get.mockResolvedValue({ data: { collections: [], exports: [] } });
    api.post.mockResolvedValueOnce({ data: { plan_id: 'p2', inspection: { can_export: true } } });
    const { result } = renderHook(() => useTranslationCollections(true));
    await act(async () => { result.current.setSelected({ collection_id: 'c2' }); });
    await act(async () => result.current.plan());
    expect(result.current.preview).toEqual({ plan_id: 'p2', inspection: { can_export: true } });
    api.post.mockResolvedValueOnce({ data: { package_path: '/out.zip' } });
    await act(async () => result.current.exportPackage());
    expect(api.post).toHaveBeenCalledWith('/api/translation-collections/c2/export', { plan_id: 'p2', approved: true });
  });

  it('does not restore an old collection when export refresh finishes after switching', async () => {
    let resolveOldDetail;
    const oldDetail = new Promise((resolve) => { resolveOldDetail = resolve; });
    api.get.mockImplementation((url) => {
      if (url === '/api/translation-collections/c1') return oldDetail;
      if (url === '/api/translation-collections/c2') return Promise.resolve({ data: { collection_id: 'c2' } });
      return Promise.resolve({ data: { collections: [], exports: [] } });
    });
    api.post.mockResolvedValueOnce({ data: { plan_id: 'p1', inspection: { can_export: true } } });
    const { result } = renderHook(() => useTranslationCollections(true));
    act(() => result.current.setSelected({ collection_id: 'c1' }));
    await act(async () => result.current.plan());
    api.post.mockResolvedValueOnce({ data: { package_path: '/old-export' } });
    let exporting;
    await act(async () => { exporting = result.current.exportPackage(); });
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/translation-collections/c1'));
    await act(async () => result.current.openCollection('c2'));
    await act(async () => {
      resolveOldDetail({ data: { collection_id: 'c1' } });
      await exporting;
    });
    expect(result.current.selected.collection_id).toBe('c2');
    expect(result.current.history).toEqual([]);
  });
});

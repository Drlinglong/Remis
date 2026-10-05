import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../utils/api';
import { useCollectionRequestLifecycle } from './useCollectionRequestLifecycle';
import { useCollectionProjectOptions } from './useCollectionProjectOptions';
import { useCollectionExportController } from './useCollectionExportController';

const base = '/api/translation-collections';

export function useTranslationCollections(opened) {
  const [collections, setCollections] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const requestId = useRef(0);
  const lifecycle = useCollectionRequestLifecycle(opened);
  const { busy, error, capture, isCurrent, isLive, nextSelection, clearError, reportError, resetSession, run } = lifecycle;
  const options = useCollectionProjectOptions({ capture, isCurrent, reportError });
  const { projectOptions, optionsLoading, loadProjectOptions, resetRequests, invalidateMembers } = options;

  const refresh = useCallback(async () => {
    const { life } = capture();
    const id = ++requestId.current;
    setLoading(true);
    clearError();
    try {
      const { data } = await api.get(base);
      if (isLive(life) && requestId.current === id) setCollections(data.collections || []);
    } catch (cause) {
      if (isLive(life) && requestId.current === id) reportError(cause);
    } finally {
      if (isLive(life) && requestId.current === id) setLoading(false);
    }
  }, [capture, clearError, isLive, reportError]);

  const onSelected = useCallback((data) => { setSelected(data); setDraftDirty(false); }, []);
  const exports = useCollectionExportController({ selected, draftDirty, capture, isCurrent, isLive,
    run, onSelected, refresh });
  const { preview, history, setHistory, readHistory, plan, exportPackage, invalidatePreview, resetExport } = exports;
  const clearSelection = useCallback(() => {
    nextSelection();
    setSelected(null);
    resetExport();
    setDraftDirty(false);
    clearError();
  }, [clearError, nextSelection, resetExport]);
  const close = useCallback(() => {
    resetSession(false);
    requestId.current += 1;
    resetRequests();
    clearSelection();
    setLoading(false);
  }, [clearSelection, resetRequests, resetSession]);

  useEffect(() => {
    if (opened) refresh();
    else {
      requestId.current += 1;
      resetRequests();
      clearSelection();
      setLoading(false);
    }
  }, [opened, refresh, resetRequests, clearSelection]);

  const create = useCallback((body) => {
    const { life } = capture();
    const selection = nextSelection();
    invalidatePreview();
    return run(async () => {
      const { data } = await api.post(base, body);
      if (isLive(life)) setCollections((current) => [data, ...current]);
      if (isCurrent(life, selection)) {
        onSelected(data);
        resetExport();
      }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [capture, invalidatePreview, isCurrent, isLive, nextSelection, onSelected, resetExport, run]);

  const openCollection = useCallback((id) => {
    const { life } = capture();
    const selection = nextSelection();
    invalidatePreview();
    setDraftDirty(false);
    return run(async () => {
      const [{ data }, collectionHistory] = await Promise.all([
        api.get(`${base}/${encodeURIComponent(id)}`), readHistory(id),
      ]);
      if (isCurrent(life, selection)) {
        onSelected(data);
        setHistory(collectionHistory);
        invalidatePreview();
        invalidateMembers(data.members);
      }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [capture, invalidateMembers, invalidatePreview, isCurrent, nextSelection, onSelected, readHistory, run, setHistory]);

  const save = useCallback((body) => {
    if (!selected) return Promise.resolve(null);
    const { life, selection } = capture();
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.put(`${base}/${encodeURIComponent(collectionId)}`, {
        expected_revision: selected.revision, ...body,
      });
      if (isLive(life)) setCollections((current) => current.map((item) => item.collection_id === collectionId ? data : item));
      if (isCurrent(life, selection)) { onSelected(data); invalidatePreview(); }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [capture, invalidatePreview, isCurrent, isLive, onSelected, run, selected]);

  const bindPublication = useCallback((steamId) => {
    if (!selected || draftDirty) return Promise.resolve(null);
    const { life, selection } = capture();
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.put(`${base}/${encodeURIComponent(collectionId)}/publication`, {
        expected_revision: selected.revision, steam_id: steamId, approved: true,
      });
      if (isLive(life)) setCollections((current) => current.map((item) => item.collection_id === collectionId ? data : item));
      if (isCurrent(life, selection)) { setSelected(data); invalidatePreview(); }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [capture, draftDirty, invalidatePreview, isCurrent, isLive, run, selected]);

  const remove = useCallback(() => {
    if (!selected) return Promise.resolve(null);
    const { life, selection } = capture();
    const collectionId = selected.collection_id;
    return run(async () => {
      await api.delete(`${base}/${encodeURIComponent(collectionId)}?expected_revision=${selected.revision}`);
      if (isLive(life)) setCollections((current) => current.filter((item) => item.collection_id !== collectionId));
      if (isCurrent(life, selection)) clearSelection();
      return collectionId;
    }, () => isCurrent(life, selection), life);
  }, [capture, clearSelection, isCurrent, isLive, run, selected]);

  const markDraftDirty = useCallback(() => { invalidatePreview(); setDraftDirty(true); }, [invalidatePreview]);
  return { collections, selected, setSelected, projectOptions, optionsLoading, preview, history, busy, loading, error,
    draftDirty, create, openCollection, clearSelection, close, loadProjectOptions, save, bindPublication, plan,
    exportPackage, remove, invalidatePreview, markDraftDirty, refresh };
}

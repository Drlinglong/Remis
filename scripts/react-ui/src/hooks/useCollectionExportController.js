import { useCallback, useRef, useState } from 'react';
import api from '../utils/api';

const base = '/api/translation-collections';

export function useCollectionExportController({ selected, draftDirty, capture, isCurrent, isLive, run,
  onSelected, refresh }) {
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);
  const previewRequestId = useRef(0);
  const invalidatePreview = useCallback(() => {
    previewRequestId.current += 1;
    setPreview(null);
  }, []);
  const resetExport = useCallback(() => {
    invalidatePreview();
    setHistory([]);
  }, [invalidatePreview]);
  const readHistory = useCallback(async (id) => {
    const { data } = await api.get(`${base}/${encodeURIComponent(id)}/history`);
    return data.exports || [];
  }, []);

  const plan = useCallback(() => {
    if (!selected || draftDirty) return Promise.resolve(null);
    const { life, selection } = capture();
    const currentRequest = ++previewRequestId.current;
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.post(`${base}/${encodeURIComponent(collectionId)}/plan`, {});
      if (isCurrent(life, selection) && previewRequestId.current === currentRequest) setPreview(data);
      return data;
    }, () => isCurrent(life, selection), life);
  }, [capture, draftDirty, isCurrent, run, selected]);

  const exportPackage = useCallback(() => {
    if (!selected || draftDirty || !preview?.plan_id || !preview.inspection?.can_export) return Promise.resolve(null);
    const { life, selection } = capture();
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.post(`${base}/${encodeURIComponent(collectionId)}/export`, {
        plan_id: preview.plan_id, approved: true,
      });
      if (isCurrent(life, selection)) {
        const [{ data: current }, exports] = await Promise.all([
          api.get(`${base}/${encodeURIComponent(collectionId)}`), readHistory(collectionId),
        ]);
        if (isCurrent(life, selection)) {
          onSelected(current);
          setHistory(exports);
          invalidatePreview();
        }
      }
      if (isLive(life)) await refresh();
      return data;
    }, () => isCurrent(life, selection), life);
  }, [capture, draftDirty, invalidatePreview, isCurrent, isLive, onSelected, preview, readHistory, refresh, run, selected]);

  return { preview, history, setHistory, readHistory, plan, exportPackage, invalidatePreview, resetExport };
}

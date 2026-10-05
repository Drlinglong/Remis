import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../utils/api';

const base = '/api/translation-collections';
const getErrorMessage = (cause) => {
  const detail = cause.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join('; ');
  return cause.message || 'Request failed';
};

export function useTranslationCollections(opened) {
  const [collections, setCollections] = useState([]);
  const [selected, setSelected] = useState(null);
  const [projectOptions, setProjectOptions] = useState({});
  const [optionsLoading, setOptionsLoading] = useState({});
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [draftDirty, setDraftDirty] = useState(false);
  const requestId = useRef(0);
  const selectedRequestId = useRef(0);
  const lifeId = useRef(0);
  const openedRef = useRef(opened);
  const busyCounts = useRef(new Map());
  const previewRequestId = useRef(0);
  const optionsInFlight = useRef(new Map());
  const projectOptionsRef = useRef(projectOptions);
  openedRef.current = opened;
  projectOptionsRef.current = projectOptions;

  const isCurrent = useCallback((life, selection) => (
    openedRef.current && lifeId.current === life && selectedRequestId.current === selection
  ), []);

  const refresh = useCallback(async () => {
    const life = lifeId.current;
    const id = ++requestId.current;
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get(base);
      if (openedRef.current && lifeId.current === life && requestId.current === id) setCollections(data.collections || []);
    } catch (cause) {
      if (openedRef.current && lifeId.current === life && requestId.current === id) setError(getErrorMessage(cause));
    } finally {
      if (openedRef.current && lifeId.current === life && requestId.current === id) setLoading(false);
    }
  }, []);

  const clearSelection = useCallback(() => {
    selectedRequestId.current += 1;
    previewRequestId.current += 1;
    setSelected(null);
    setHistory([]);
    setPreview(null);
    setDraftDirty(false);
    setError('');
  }, []);

  const close = useCallback(() => {
    openedRef.current = false;
    lifeId.current += 1;
    requestId.current += 1;
    optionsInFlight.current.clear();
    setOptionsLoading({});
    clearSelection();
    setLoading(false);
    setBusy(false);
  }, [clearSelection]);

  useEffect(() => {
    if (opened) {
      lifeId.current += 1;
      setBusy(false);
      refresh();
    } else {
      openedRef.current = false;
      lifeId.current += 1;
      requestId.current += 1;
      optionsInFlight.current.clear();
      setOptionsLoading({});
      clearSelection();
      setLoading(false);
      setBusy(false);
    }
  }, [opened, refresh, clearSelection]);

  const run = useCallback(async (operation, guard = () => openedRef.current, life = lifeId.current) => {
    busyCounts.current.set(life, (busyCounts.current.get(life) || 0) + 1);
    if (lifeId.current === life) setBusy(true);
    setError('');
    try { return await operation(); }
    catch (cause) {
      if (guard()) setError(getErrorMessage(cause));
      return null;
    } finally {
      const remaining = (busyCounts.current.get(life) || 1) - 1;
      if (remaining > 0) busyCounts.current.set(life, remaining);
      else busyCounts.current.delete(life);
      if (lifeId.current === life) setBusy(remaining > 0);
    }
  }, []);

  const create = useCallback((body) => {
    const life = lifeId.current;
    const selection = ++selectedRequestId.current;
    previewRequestId.current += 1;
    return run(async () => {
      const { data } = await api.post(base, body);
      if (lifeId.current === life && openedRef.current) setCollections((current) => [data, ...current]);
      if (isCurrent(life, selection)) {
        setSelected(data);
        setHistory([]);
        setPreview(null);
        setDraftDirty(false);
      }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [isCurrent, run]);

  const openCollection = useCallback((id) => {
    const life = lifeId.current;
    const selection = ++selectedRequestId.current;
    previewRequestId.current += 1;
    setPreview(null);
    setDraftDirty(false);
    return run(async () => {
      const [{ data }, historyResponse] = await Promise.all([
        api.get(`${base}/${encodeURIComponent(id)}`),
        api.get(`${base}/${encodeURIComponent(id)}/history`),
      ]);
      if (isCurrent(life, selection)) {
        setSelected(data);
        setHistory(historyResponse.data.exports || []);
        setPreview(null);
        setDraftDirty(false);
        setProjectOptions((current) => {
          const next = { ...current };
          (data.members || []).forEach((member) => { delete next[member.project_id]; });
          return next;
        });
      }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [isCurrent, run]);

  const loadProjectOptions = useCallback((projectId, force = false) => {
    if (!force && projectOptionsRef.current[projectId]) return Promise.resolve(projectOptionsRef.current[projectId]);
    const life = lifeId.current;
    const selection = selectedRequestId.current;
    const existing = optionsInFlight.current.get(projectId);
    // A new collection must own its request even when it shares a member project.
    if (existing?.life === life && existing.selection === selection) return existing.request;
    setOptionsLoading((current) => ({ ...current, [projectId]: true }));
    const request = api.get(`${base}/project-options/${encodeURIComponent(projectId)}`)
      .then(({ data }) => {
        if (isCurrent(life, selection)) setProjectOptions((current) => ({ ...current, [projectId]: data }));
        return data;
      })
      .catch((cause) => {
        if (isCurrent(life, selection)) setError(getErrorMessage(cause));
        return null;
      })
      .finally(() => {
        if (optionsInFlight.current.get(projectId)?.request === request) {
          optionsInFlight.current.delete(projectId);
          if (isCurrent(life, selection)) setOptionsLoading((current) => ({ ...current, [projectId]: false }));
        }
      });
    optionsInFlight.current.set(projectId, { life, selection, request });
    return request;
  }, [isCurrent]);

  const save = useCallback((body) => {
    if (!selected) return Promise.resolve(null);
    const life = lifeId.current;
    const selection = selectedRequestId.current;
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.put(`${base}/${encodeURIComponent(collectionId)}`, {
        expected_revision: selected.revision,
        ...body,
      });
      if (lifeId.current === life && openedRef.current) {
        setCollections((current) => current.map((item) => item.collection_id === collectionId ? data : item));
      }
      if (isCurrent(life, selection)) {
        setSelected(data);
        setPreview(null);
        setDraftDirty(false);
      }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [isCurrent, run, selected]);

  const bindPublication = useCallback((steamId) => {
    if (!selected || draftDirty) return Promise.resolve(null);
    const life = lifeId.current;
    const selection = selectedRequestId.current;
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.put(`${base}/${encodeURIComponent(collectionId)}/publication`, {
        expected_revision: selected.revision, steam_id: steamId, approved: true,
      });
      if (lifeId.current === life && openedRef.current) {
        setCollections((current) => current.map((item) => item.collection_id === collectionId ? data : item));
      }
      if (isCurrent(life, selection)) {
        setSelected(data);
        setPreview(null);
      }
      return data;
    }, () => isCurrent(life, selection), life);
  }, [draftDirty, isCurrent, run, selected]);

  const plan = useCallback(() => {
    if (!selected || draftDirty) return Promise.resolve(null);
    const life = lifeId.current;
    const selection = selectedRequestId.current;
    const currentRequest = ++previewRequestId.current;
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.post(`${base}/${encodeURIComponent(collectionId)}/plan`, {});
      if (isCurrent(life, selection) && previewRequestId.current === currentRequest) setPreview(data);
      return data;
    }, () => isCurrent(life, selection), life);
  }, [draftDirty, isCurrent, run, selected]);

  const exportPackage = useCallback(() => {
    if (!selected || draftDirty || !preview?.plan_id || !preview.inspection?.can_export) return Promise.resolve(null);
    const life = lifeId.current;
    const selection = selectedRequestId.current;
    const collectionId = selected.collection_id;
    return run(async () => {
      const { data } = await api.post(`${base}/${encodeURIComponent(collectionId)}/export`, {
        plan_id: preview.plan_id, approved: true,
      });
      if (isCurrent(life, selection)) {
        const [{ data: current }, historyResponse] = await Promise.all([
          api.get(`${base}/${encodeURIComponent(collectionId)}`),
          api.get(`${base}/${encodeURIComponent(collectionId)}/history`),
        ]);
        if (isCurrent(life, selection)) {
          setSelected(current);
          setHistory(historyResponse.data.exports || []);
          setPreview(null);
          setDraftDirty(false);
        }
      }
      if (lifeId.current === life && openedRef.current) await refresh();
      return data;
    }, () => isCurrent(life, selection), life);
  }, [draftDirty, isCurrent, preview, refresh, run, selected]);

  const remove = useCallback(() => {
    if (!selected) return Promise.resolve(null);
    const life = lifeId.current;
    const selection = selectedRequestId.current;
    const collectionId = selected.collection_id;
    return run(async () => {
      await api.delete(`${base}/${encodeURIComponent(collectionId)}?expected_revision=${selected.revision}`);
      if (lifeId.current === life && openedRef.current) setCollections((current) => current.filter((item) => item.collection_id !== collectionId));
      if (isCurrent(life, selection)) clearSelection();
      return collectionId;
    }, () => isCurrent(life, selection), life);
  }, [clearSelection, isCurrent, run, selected]);

  const invalidatePreview = useCallback(() => {
    previewRequestId.current += 1;
    setPreview(null);
  }, []);
  const markDraftDirty = useCallback(() => {
    previewRequestId.current += 1;
    setPreview(null);
    setDraftDirty(true);
  }, []);

  return { collections, selected, setSelected, projectOptions, optionsLoading, preview, history, busy, loading, error,
    draftDirty, create, openCollection, clearSelection, close, loadProjectOptions, save, bindPublication, plan,
    exportPackage, remove, invalidatePreview, markDraftDirty, refresh };
}

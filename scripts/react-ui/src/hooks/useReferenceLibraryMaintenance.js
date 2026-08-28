import { useCallback, useEffect, useRef, useState } from 'react';

import translationService from '../services/translationService';

const ACTIVE_STATUSES = new Set([
  'queued', 'pending', 'running', 'discovering', 'scanning', 'indexing', 'activating',
]);
const TERMINAL_STATUSES = new Set([
  'completed', 'success', 'failed', 'partial_failed', 'cancelled', 'canceled', 'interrupted',
]);

const unwrap = (payload) => {
  let value = payload;
  for (let depth = 0; depth < 3; depth += 1) {
    if (!value || typeof value !== 'object') return {};
    if (value.data && typeof value.data === 'object' && (
      typeof value.status === 'number' || Object.keys(value).length === 1
    )) {
      value = value.data;
      continue;
    }
    return value;
  }
  return value || {};
};

const taskIdFrom = (payload) => {
  const value = unwrap(payload);
  return value.task_id || value.job_id || value.id
    || value.task?.task_id || value.active_task?.task_id || value.job?.task_id || null;
};

const isActiveTask = (task) => Boolean(
  task?.task_id && !TERMINAL_STATUSES.has(task.status) && task.status !== 'not_found',
);

const candidatePath = (candidate) => candidate.localization_path || candidate.root_path || '';

const normalizeCandidate = (candidate = {}, library = {}) => {
  const available = candidate.available ?? library.available ?? false;
  const stale = candidate.stale ?? library.stale ?? false;
  return {
    ...library,
    ...candidate,
    localization_path: candidatePath(candidate) || candidatePath(library),
    available,
    stale,
    status: candidate.status || (available ? (stale ? 'stale' : 'ready') : 'missing'),
  };
};

const normalizeTask = (payload, fallbackTaskId = null) => {
  const value = unwrap(payload);
  const task = [value.task, value.active_task, value.job]
    .find((candidate) => candidate && typeof candidate === 'object') || value;
  const taskId = taskIdFrom(task) || fallbackTaskId;
  if (!taskId && !task.status) return null;
  return { ...task, task_id: taskId, progress: task.progress || {} };
};

export const referenceLibraryTaskIsActive = isActiveTask;

export default function useReferenceLibraryMaintenance() {
  const [libraries, setLibraries] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [task, setTask] = useState(null);
  const [discoveryOpen, setDiscoveryOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const generationRef = useRef(0);

  const refresh = useCallback(async () => {
    const response = await translationService.getReferenceLibraryStatus();
    const payload = unwrap(response);
    setLibraries(payload.libraries || []);
    return payload;
  }, []);

  const refreshTask = useCallback(async (taskId) => {
    if (!taskId) return null;
    const response = await translationService.getReferenceLibraryJob(taskId);
    const nextTask = normalizeTask(response, taskId);
    if (nextTask) setTask(nextTask);
    return nextTask;
  }, []);

  const restoreActiveTask = useCallback(async () => {
    try {
      const response = await translationService.getActiveReferenceLibraryJob();
      const nextTask = normalizeTask(response);
      if (nextTask && isActiveTask(nextTask)) {
        setTask(nextTask);
        setTaskOpen(true);
        return nextTask;
      }
    } catch (restoreError) {
      // A 404 simply means that no maintenance job is currently running.
      if (restoreError?.response?.status !== 404) throw restoreError;
    }
    return null;
  }, []);

  useEffect(() => {
    const generation = generationRef.current;
    Promise.all([refresh(), restoreActiveTask()]).catch((loadError) => {
      if (generation === generationRef.current) {
        setError(loadError?.response?.data?.detail || loadError.message);
      }
    });
    return () => { generationRef.current += 1; };
  }, [refresh, restoreActiveTask]);

  useEffect(() => {
    if (!isActiveTask(task)) return undefined;
    const generation = generationRef.current;
    const poll = async () => {
      try {
        const nextTask = await refreshTask(task.task_id);
        if (generation !== generationRef.current || !nextTask) return;
        if (!isActiveTask(nextTask)) await refresh();
      } catch (pollError) {
        if (generation === generationRef.current) {
          setError(pollError?.response?.data?.detail || pollError.message);
        }
      }
    };
    const timer = window.setInterval(() => { void poll(); }, 1000);
    return () => window.clearInterval(timer);
  }, [refresh, refreshTask, task]);

  const openDiscovery = useCallback(async (manualCandidate = null) => {
    setError(null);
    setLoading(true);
    try {
      const response = manualCandidate
        ? { data: { candidates: [manualCandidate] } }
        : await translationService.discoverReferenceLibraries();
      const payload = unwrap(response);
      const currentByGame = new Map(libraries.map((library) => [library.game_id, library]));
      const nextCandidates = (payload.candidates || []).map((candidate) => (
        normalizeCandidate(candidate, currentByGame.get(candidate.game_id))
      ));
      setCandidates(nextCandidates);
      setSelectedIds(new Set(nextCandidates
        .filter((candidate) => ['missing', 'stale'].includes(candidate.status))
        .map((candidate) => candidate.game_id)));
      setDiscoveryOpen(true);
      return nextCandidates;
    } catch (discoveryError) {
      setError(discoveryError?.response?.data?.detail || discoveryError.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [libraries]);

  const toggleCandidate = useCallback((gameId) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(gameId)) next.delete(gameId);
      else next.add(gameId);
      return next;
    });
  }, []);

  const startTask = useCallback(async (operations) => {
    setError(null);
    setLoading(true);
    try {
      const response = await translationService.startReferenceLibraryJob({ operations });
      const nextTask = normalizeTask(response, taskIdFrom(response));
      if (nextTask) {
        setTask(nextTask);
        setTaskOpen(true);
      }
      setDiscoveryOpen(false);
      return nextTask;
    } catch (startError) {
      if (startError?.response?.status === 409) {
        const existingId = taskIdFrom(startError.response?.data);
        if (existingId) {
          const existingTask = await refreshTask(existingId);
          setTask(existingTask);
          setTaskOpen(true);
          setDiscoveryOpen(false);
          return existingTask;
        }
      }
      setError(startError?.response?.data?.detail || startError.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [refreshTask]);

  const confirmDiscovery = useCallback(() => {
    const operations = candidates
      .filter((candidate) => selectedIds.has(candidate.game_id))
      .map((candidate) => ({
        game_id: candidate.game_id,
        localization_path: candidatePath(candidate),
        action: candidate.status === 'stale' ? 'update' : 'build',
      }));
    return startTask(operations);
  }, [candidates, selectedIds, startTask]);

  const deleteLibrary = useCallback(async (gameId) => {
    setError(null);
    setLoading(true);
    try {
      const response = await translationService.deleteReferenceLibrary(gameId);
      const nextTask = normalizeTask(response, taskIdFrom(response));
      if (nextTask) {
        setTask(nextTask);
        setTaskOpen(true);
      } else {
        await refresh();
      }
      return nextTask;
    } catch (deleteError) {
      setError(deleteError?.response?.data?.detail || deleteError.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  return {
    libraries,
    candidates,
    selectedIds,
    task,
    discoveryOpen,
    taskOpen,
    loading,
    error,
    setDiscoveryOpen,
    setTaskOpen,
    toggleCandidate,
    openDiscovery,
    confirmDiscovery,
    deleteLibrary,
    refresh,
  };
}

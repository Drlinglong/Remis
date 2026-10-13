import { useCallback, useEffect, useRef, useState } from 'react';
import { workshopPublicationService as service } from '../../../services/workshopPublicationService';

const errorDetail = (error) => {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : detail?.message || error.message;
};

export function useWorkshopPublication(workspaceId) {
  const [options, setOptions] = useState(null);
  const [history, setHistory] = useState([]);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const revision = useRef(0);
  const mounted = useRef(false);
  const submitting = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const records = await service.history(workspaceId);
      if (mounted.current) setHistory(Array.isArray(records) ? records : []);
    } catch (requestError) {
      if (mounted.current) setError(errorDetail(requestError));
    }
  }, [workspaceId]);

  useEffect(() => {
    mounted.current = true;
    let active = true;
    service.options(workspaceId).then((value) => {
      if (active) setOptions(value);
    }).catch((requestError) => {
      if (active) setError(errorDetail(requestError));
    });
    refresh();
    return () => {
      active = false;
      mounted.current = false;
      revision.current += 1;
    };
  }, [refresh, workspaceId]);

  useEffect(() => {
    if (!history.some((record) => record.status === 'running')) return undefined;
    const interval = setInterval(refresh, 2000);
    return () => clearInterval(interval);
  }, [history, refresh]);

  const invalidate = useCallback(() => {
    revision.current += 1;
    setPreview(null);
    setError('');
  }, []);

  const createPreview = useCallback(async (request) => {
    const current = ++revision.current;
    setPreview(null);
    setError('');
    setBusy(true);
    try {
      const result = await service.plan(workspaceId, request);
      if (mounted.current && revision.current === current) setPreview(result);
      await refresh();
    } catch (requestError) {
      if (mounted.current && revision.current === current) setError(errorDetail(requestError));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [refresh, workspaceId]);

  const submit = useCallback(async () => {
    if (!preview?.allowed_actions?.includes('approve_publication') || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      const result = await service.submit(workspaceId, preview);
      if (mounted.current) setPreview(result);
    } catch (requestError) {
      if (mounted.current) {
        setPreview(null);
        setError(errorDetail(requestError));
      }
    } finally {
      submitting.current = false;
      if (mounted.current) setBusy(false);
      await refresh();
    }
  }, [preview, refresh, workspaceId]);

  const current = history.find((record) => record.plan_id === preview?.plan_id) || preview;
  const verify = useCallback(async (planId, request) => {
    setBusy(true);
    setError('');
    try {
      await service.verify(workspaceId, planId, request);
      invalidate();
      await refresh();
      return true;
    } catch (requestError) {
      if (mounted.current) setError(errorDetail(requestError));
      return false;
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [invalidate, refresh, workspaceId]);
  return { options, history, preview: current, busy, error, createPreview, invalidate, submit, verify, refresh };
}

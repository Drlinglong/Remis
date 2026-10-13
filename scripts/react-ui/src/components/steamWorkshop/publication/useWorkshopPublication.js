import { useCallback, useEffect, useRef, useState } from 'react';
import { workshopPublicationService as service } from '../../../services/workshopPublicationService';
import { publicationErrorDetail as errorDetail } from './publicationValidation';
import { latestPublicationRecord, mergePublicationHistory } from './publicationHistory';

export function useWorkshopPublication(workspaceId) {
  const [options, setOptions] = useState(null);
  const [history, setHistory] = useState([]);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const revision = useRef(0);
  const mounted = useRef(false);
  const submitting = useRef(false);
  const historyRequest = useRef(0);
  const historyPending = useRef(false);
  const current = latestPublicationRecord(preview, history.find((record) => record.plan_id === preview?.plan_id));

  const refresh = useCallback(async () => {
    const request = ++historyRequest.current;
    historyPending.current = true;
    try {
      const records = await service.history(workspaceId);
      if (mounted.current && request === historyRequest.current) {
        setHistory((previous) => mergePublicationHistory(previous, Array.isArray(records) ? records : []));
      }
    } catch (requestError) {
      if (mounted.current && request === historyRequest.current) setError(errorDetail(requestError));
    } finally {
      if (request === historyRequest.current) historyPending.current = false;
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
      historyRequest.current += 1;
    };
  }, [refresh, workspaceId]);

  useEffect(() => {
    if (!history.some((record) => record.status === 'running')) return undefined;
    const interval = setInterval(() => {
      if (!historyPending.current) refresh();
    }, 2000);
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
    if (!current?.allowed_actions?.includes('approve_publication') || submitting.current) return;
    submitting.current = true;
    historyRequest.current += 1;
    setBusy(true);
    setError('');
    try {
      const result = await service.submit(workspaceId, current);
      historyRequest.current += 1;
      if (mounted.current) {
        setPreview(result);
        setHistory((previous) => previous.map((record) => record.plan_id === result.plan_id
          ? latestPublicationRecord(record, result) : record));
      }
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
  }, [current, refresh, workspaceId]);

  const verify = useCallback(async (planId, request) => {
    setBusy(true);
    setError('');
    historyRequest.current += 1;
    try {
      await service.verify(workspaceId, planId, request);
      if (!mounted.current) return false;
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

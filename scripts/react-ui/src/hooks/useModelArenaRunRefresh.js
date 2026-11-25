import { useCallback, useEffect, useLayoutEffect, useRef } from 'react';
import modelArenaService from '../services/modelArenaService';
import { apiErrorDetail } from '../utils/apiErrorDetail';
import { useRequestScope } from './useRequestScope';

export function useModelArenaRunRefresh({ run, requestedRunId, applyRun, setError, errorFallback }) {
  const { begin, invalidate } = useRequestScope();
  const refreshing = useRef(false);
  const runId = run?.run_id;
  const status = run?.status;
  const invalidateRefresh = useCallback(() => {
    invalidate();
    refreshing.current = false;
  }, [invalidate]);
  useLayoutEffect(() => invalidateRefresh, [runId, status, requestedRunId, invalidateRefresh]);

  const refreshRun = useCallback(async () => {
    if (!runId || (requestedRunId && requestedRunId !== runId)) return;
    const isCurrent = begin('refresh');
    refreshing.current = true;
    try {
      const nextRun = await modelArenaService.getRun(runId);
      if (!isCurrent() || nextRun?.run_id !== runId) return;
      applyRun(nextRun);
      setError('');
    } catch (error) {
      if (isCurrent()) setError(apiErrorDetail(error, errorFallback));
    } finally {
      if (isCurrent()) refreshing.current = false;
    }
  }, [applyRun, begin, errorFallback, requestedRunId, runId, setError]);

  useEffect(() => {
    if (!runId || !['queued', 'running'].includes(status)) return undefined;
    const intervalId = window.setInterval(() => {
      if (!refreshing.current) refreshRun();
    }, 1500);
    return () => window.clearInterval(intervalId);
  }, [refreshRun, runId, status]);

  return { refreshRun, invalidateRefresh };
}

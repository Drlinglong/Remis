import { useCallback, useEffect, useRef, useState } from 'react';

const errorMessage = (cause) => {
  const detail = cause.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join('; ');
  return cause.message || 'Request failed';
};

export function useCollectionRequestLifecycle(opened) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lifeId = useRef(0);
  const selectionId = useRef(0);
  const openedRef = useRef(opened);
  const busyCounts = useRef(new Map());
  openedRef.current = opened;

  const capture = useCallback(() => ({ life: lifeId.current, selection: selectionId.current }), []);
  const isLive = useCallback((life) => openedRef.current && lifeId.current === life, []);
  const isCurrent = useCallback((life, selection) => (
    openedRef.current && lifeId.current === life && selectionId.current === selection
  ), []);
  const nextSelection = useCallback(() => ++selectionId.current, []);
  const clearError = useCallback(() => setError(''), []);
  const reportError = useCallback((cause) => setError(errorMessage(cause)), []);
  const resetSession = useCallback((open) => {
    openedRef.current = open;
    lifeId.current += 1;
    selectionId.current += 1;
    setBusy(false);
    setError('');
  }, []);

  useEffect(() => {
    resetSession(opened);
    return () => { openedRef.current = false; lifeId.current += 1; };
  }, [opened, resetSession]);

  const run = useCallback(async (operation, guard, life = lifeId.current) => {
    const current = guard || (() => isLive(life));
    busyCounts.current.set(life, (busyCounts.current.get(life) || 0) + 1);
    if (isLive(life)) setBusy(true);
    clearError();
    try { return await operation(); }
    catch (cause) {
      if (current()) reportError(cause);
      return null;
    } finally {
      const remaining = (busyCounts.current.get(life) || 1) - 1;
      if (remaining > 0) busyCounts.current.set(life, remaining);
      else busyCounts.current.delete(life);
      if (isLive(life)) setBusy(remaining > 0);
    }
  }, [clearError, isLive, reportError]);

  return { busy, error, capture, isLive, isCurrent, nextSelection, clearError, reportError, resetSession, run };
}

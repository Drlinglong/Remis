import { useEffect, useRef, useState } from 'react';

export const COPILOT_STALL_MS = 3 * 60 * 1000;

/** Quiet reminder timer. Background time does not count as stalled time. */
export function useCopilotStallReminder({
  enabled = true,
  meaningfulState,
  error = null,
  blocked = false,
  openingMessage,
  stallMs = COPILOT_STALL_MS,
}) {
  const [reminder, setReminder] = useState(null);
  const remainingRef = useRef(stallMs);
  const startedAtRef = useRef(0);

  useEffect(() => {
    remainingRef.current = stallMs;
    setReminder(null);
  }, [meaningfulState, stallMs]);

  useEffect(() => {
    if (!enabled) {
      setReminder(null);
      return undefined;
    }
    if (error || blocked) {
      setReminder({
        reason: error ? 'error' : 'blocked',
        detectedAt: new Date().toISOString(),
        openingMessage,
      });
      return undefined;
    }

    let timeoutId;
    const start = () => {
      if (document.visibilityState === 'hidden') return;
      startedAtRef.current = Date.now();
      timeoutId = window.setTimeout(() => {
        setReminder({ reason: 'stalled', detectedAt: new Date().toISOString(), openingMessage });
      }, remainingRef.current);
    };
    const pauseOrResume = () => {
      window.clearTimeout(timeoutId);
      if (document.visibilityState === 'hidden') {
        remainingRef.current = Math.max(0, remainingRef.current - (Date.now() - startedAtRef.current));
      } else {
        start();
      }
    };
    start();
    document.addEventListener('visibilitychange', pauseOrResume);
    return () => {
      window.clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', pauseOrResume);
    };
  }, [blocked, enabled, error, meaningfulState, openingMessage, stallMs]);

  return reminder;
}

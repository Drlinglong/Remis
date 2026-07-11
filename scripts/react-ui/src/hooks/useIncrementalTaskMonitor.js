import { useCallback, useEffect, useRef } from 'react';

import projectService from '../services/projectService';

export function useIncrementalTaskMonitor({
  addLog,
  executionInFlightRef,
  preScanInFlightRef,
  setActive,
  setCurrentTaskId,
  setCurrentTaskMode,
  setExecuting,
  setFinalSummary,
  setLoading,
  setLogs,
  setProgress,
  setProgressInfo,
  setScanResults,
  t,
}) {
  const wsRef = useRef(null);
  const pollTimerRef = useRef(null);
  const completionSourceRef = useRef(null);

  const clearTaskPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const closeTaskSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const handleTaskUpdate = useCallback((data, isPreScan = false, source = 'unknown') => {
    if (!data) return;

    if (data.progress) {
      setProgress(data.progress.percent || 0);
      setProgressInfo(data.progress);
    }

    if (data.log) {
      setLogs(data.log);
    }

    if (data.status === 'completed') {
      completionSourceRef.current = source;
      console.info(`Incremental task completed via ${source}.`);
      clearTaskPolling();

      if (isPreScan) {
        preScanInFlightRef.current = false;
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        setScanResults({
          ...(data.summary || {}),
          file_summaries: data.file_summaries || [],
          telemetry: data.telemetry || null,
        });
        setActive(2);
        setLoading(false);
      } else {
        executionInFlightRef.current = false;
        setFinalSummary(data);
        addLog(t('incremental_translation.translation_completed_success'));
        setProgress(100);
        setProgressInfo(data.progress || {});
        setExecuting(false);
      }

      closeTaskSocket();
      return;
    }

    if (data.status === 'failed') {
      completionSourceRef.current = source;
      console.warn(`Incremental task failed via ${source}.`);
      clearTaskPolling();
      addLog(t('incremental_translation.task_failed_check_logs'));

      if (isPreScan) {
        preScanInFlightRef.current = false;
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        setLoading(false);
      } else {
        executionInFlightRef.current = false;
        setExecuting(false);
      }

      closeTaskSocket();
    }
  }, [
    addLog,
    clearTaskPolling,
    closeTaskSocket,
    executionInFlightRef,
    preScanInFlightRef,
    setActive,
    setCurrentTaskId,
    setCurrentTaskMode,
    setExecuting,
    setFinalSummary,
    setLoading,
    setLogs,
    setProgress,
    setProgressInfo,
    setScanResults,
    t,
  ]);

  const startTaskPolling = useCallback((taskId, isPreScan = false) => {
    clearTaskPolling();
    console.info(`Starting polling fallback for incremental task ${taskId}.`);
    pollTimerRef.current = setInterval(async () => {
      try {
        const response = await projectService.getTaskStatus(taskId);
        handleTaskUpdate(response.data, isPreScan, 'polling');
      } catch (error) {
        console.error('Polling task status failed:', error);
      }
    }, 1000);
  }, [clearTaskPolling, handleTaskUpdate]);

  const connectWebSocket = useCallback((taskId, isPreScan = false) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/status/${taskId}`;

    console.log(`Connecting to WS (${isPreScan ? 'Pre-scan' : 'Execution'}): ${wsUrl}`);
    closeTaskSocket();
    startTaskPolling(taskId, isPreScan);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.info(`Incremental task WebSocket connected: ${taskId}`);
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error('Failed to parse incremental task WebSocket message:', error);
        if (!completionSourceRef.current && wsRef.current === ws) {
          addLog(t('incremental_translation.status_ws_error'));
        }
        return;
      }
      handleTaskUpdate(data, isPreScan, 'websocket');
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      if (completionSourceRef.current || wsRef.current !== ws) {
        return;
      }
      addLog(t('incremental_translation.status_ws_error'));
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed.');
    };
  }, [addLog, closeTaskSocket, handleTaskUpdate, startTaskPolling, t]);

  useEffect(() => () => {
    clearTaskPolling();
    closeTaskSocket();
  }, [clearTaskPolling, closeTaskSocket]);

  return {
    clearTaskPolling,
    completionSourceRef,
    connectWebSocket,
    handleTaskUpdate,
  };
}

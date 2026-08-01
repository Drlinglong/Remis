import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  createAgentWorkshopSnapshot,
  writeAgentWorkshopSnapshot,
} from './agentWorkshopSession';
import { pollAgentWorkshopRun } from './agentWorkshopRunMonitor';
import {
  createAgentWorkshopIdempotencyKey,
  getAgentWorkshopRunStatus,
  isRepairableAgentWorkshopIssue,
  startAgentWorkshopFixRun,
} from '../services/agentWorkshopWorkflowService';
import { formatCurrentLocalizedDateTime } from '../utils/localizedDateTime';

export const useAgentWorkshopRunController = ({
  baseSessionState,
  issues,
  restoredRef,
  selectedModel,
  selectedProjectId,
  selectedProvider,
  setActive,
  setFixedIssues,
  setIssues,
  setWorkflowError,
  t,
}) => {
  const [batchSizeLimit, setBatchSizeLimit] = useState('10');
  const [concurrencyLimit, setConcurrencyLimit] = useState('1');
  const [rpmLimit, setRpmLimit] = useState('40');
  const [executing, setExecuting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [executionStats, setExecutionStats] = useState(null);
  const [currentRunTaskId, setCurrentRunTaskId] = useState(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const runResumeRef = useRef(false);
  const fixRunInFlightRef = useRef(false);
  const fixRunIdempotencyKeyRef = useRef(null);

  const sessionState = useMemo(() => ({
    ...baseSessionState,
    batchSizeLimit,
    concurrencyLimit,
    rpmLimit,
    executing,
    progress,
    executionLogs,
    executionStats,
    currentRunTaskId,
  }), [
    baseSessionState,
    batchSizeLimit,
    concurrencyLimit,
    rpmLimit,
    executing,
    progress,
    executionLogs,
    executionStats,
    currentRunTaskId,
  ]);

  const persistState = useCallback((override = {}) => {
    writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, override));
  }, [sessionState]);

  const addExecutionLog = useCallback((message) => {
    setExecutionLogs((previousLogs) => {
      const nextLogs = [...previousLogs, `[${formatCurrentLocalizedDateTime(Date.now(), { timeStyle: 'medium' })}] ${message}`];
      writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, {
        executionLogs: nextLogs,
      }));
      return nextLogs;
    });
  }, [sessionState]);

  const applyRunTaskStatus = useCallback((task, runIssues = issues) => {
    const taskProgress = task?.progress || {};
    const resolvedTaskId = task?.task_id || currentRunTaskId;
    if (typeof taskProgress.percent === 'number') {
      setProgress(taskProgress.percent);
    }
    if (Array.isArray(task?.log)) {
      setExecutionLogs(task.log);
    }
    if (task?.summary) {
      const summary = task.summary;
      setExecutionStats({
        total: summary.total || 0,
        completed: summary.completed || 0,
        successCount: summary.successCount || 0,
        failedCount: summary.failedCount || 0,
        durationMs: summary.durationMs || 0,
        batchSize: summary.batchSize || Number(batchSizeLimit) || 10,
        totalBatches: summary.totalBatches || 0,
      });
    }

    if (task?.status === 'completed' || task?.status === 'partial_failed') {
      const results = Array.isArray(task?.summary?.results) ? task.summary.results : [];
      const successfulByKey = new Map(
        results
          .filter((result) => result.status === 'SUCCESS')
          .map((result) => [`${result.file_name}::${result.key}`, result])
      );
      setFixedIssues((previousIssues) => [
        ...runIssues
          .filter((issue) => successfulByKey.has(`${issue.file_name}::${issue.key}`))
          .map((issue) => ({
            ...issue,
            ...successfulByKey.get(`${issue.file_name}::${issue.key}`),
          })),
        ...previousIssues,
      ]);
      setIssues((previousIssues) => previousIssues.filter(
        (issue) => !successfulByKey.has(`${issue.file_name}::${issue.key}`)
      ));
      setProgress(100);
      setExecuting(false);
      persistState({
        active: 3,
        progress: 100,
        executionStats: task.summary,
        executing: false,
        currentRunTaskId: resolvedTaskId,
      });
      return true;
    }

    if (['failed', 'cancelled', 'interrupted'].includes(task?.status)) {
      addExecutionLog(task.message || 'Format Repair run failed.');
      setExecuting(false);
      persistState({
        executing: false,
        currentRunTaskId: resolvedTaskId,
      });
      return true;
    }

    return false;
  }, [addExecutionLog, batchSizeLimit, currentRunTaskId, issues, persistState, setFixedIssues, setIssues]);

  const applyRunTaskStatusRef = useRef(applyRunTaskStatus);
  const addExecutionLogRef = useRef(addExecutionLog);

  useEffect(() => {
    applyRunTaskStatusRef.current = applyRunTaskStatus;
    addExecutionLogRef.current = addExecutionLog;
  }, [addExecutionLog, applyRunTaskStatus]);

  useEffect(() => {
    if (!restoredRef.current || runResumeRef.current || !executing || !currentRunTaskId) return;

    let cancelled = false;
    runResumeRef.current = true;

    pollAgentWorkshopRun({
      taskId: currentRunTaskId,
      getStatus: getAgentWorkshopRunStatus,
      onTask: (task) => applyRunTaskStatusRef.current(task),
      isCancelled: () => cancelled,
    }).catch((error) => {
      if (cancelled) return;
      console.error('Failed to resume Format Repair run', error);
      const detail = error?.response?.data?.detail;
      const message = detail?.message || detail || error.message || 'Format Repair run failed.';
      addExecutionLogRef.current(message);
      setWorkflowError(message);
      setExecuting(false);
    });

    return () => {
      cancelled = true;
    };
  }, [currentRunTaskId, executing, restoredRef, setWorkflowError]);

  const requestFixRunApproval = useCallback(() => {
    if (!selectedProjectId || !issues.some(isRepairableAgentWorkshopIssue) || !selectedProvider || !selectedModel || executing) return;
    if (!fixRunIdempotencyKeyRef.current) {
      fixRunIdempotencyKeyRef.current = createAgentWorkshopIdempotencyKey(selectedProjectId);
    }
    setWorkflowError('');
    setApprovalOpen(true);
  }, [executing, issues, selectedModel, selectedProjectId, selectedProvider, setWorkflowError]);

  const executeFixRun = useCallback(async () => {
    if (
      !selectedProjectId
      || !issues.some(isRepairableAgentWorkshopIssue)
      || !selectedProvider
      || !selectedModel
      || executing
      || fixRunInFlightRef.current
    ) return;

    const runIssues = issues.filter(isRepairableAgentWorkshopIssue);
    fixRunInFlightRef.current = true;
    const idempotencyKey = fixRunIdempotencyKeyRef.current
      || createAgentWorkshopIdempotencyKey(selectedProjectId);
    fixRunIdempotencyKeyRef.current = idempotencyKey;
    setApprovalOpen(false);
    setWorkflowError('');
    runResumeRef.current = false;
    setExecuting(true);
    setProgress(0);
    setExecutionLogs([]);
    setExecutionStats(null);
    setCurrentRunTaskId(null);
    setActive(3);
    persistState({
      active: 3,
      executing: true,
      progress: 0,
      executionLogs: [],
      executionStats: null,
      currentRunTaskId: null,
    });

    try {
      const run = await startAgentWorkshopFixRun({
        batchSizeLimit,
        concurrencyLimit,
        issues: runIssues,
        projectId: selectedProjectId,
        rpmLimit,
        selectedModel,
        selectedProvider,
        idempotencyKey,
      });
      setCurrentRunTaskId(run.task_id);
      addExecutionLog(t('agent_workshop.task_accepted_log', {
        taskId: run.task_id,
        defaultValue: `Task accepted: ${run.task_id}`,
      }));
      persistState({
        active: 3,
        executing: true,
        currentRunTaskId: run.task_id,
      });

      await pollAgentWorkshopRun({
        taskId: run.task_id,
        getStatus: getAgentWorkshopRunStatus,
        onTask: (task) => applyRunTaskStatus(task, runIssues),
      });
    } catch (error) {
      console.error('Format Repair run failed', error);
      const detail = error?.response?.data?.detail;
      const message = detail?.message || detail || error.message || 'Format Repair run failed.';
      addExecutionLog(message);
      setWorkflowError(message);
    } finally {
      fixRunInFlightRef.current = false;
      setExecuting(false);
    }
  }, [
    addExecutionLog,
    applyRunTaskStatus,
    batchSizeLimit,
    concurrencyLimit,
    executing,
    issues,
    persistState,
    rpmLimit,
    selectedModel,
    selectedProjectId,
    selectedProvider,
    setActive,
    setWorkflowError,
    t,
  ]);

  const restoreRunState = useCallback((persisted, defaultBatchSize) => {
    setBatchSizeLimit(persisted.batchSizeLimit || defaultBatchSize);
    setConcurrencyLimit(persisted.concurrencyLimit || '1');
    setRpmLimit(persisted.rpmLimit || '40');
    setExecuting(Boolean(persisted.executing));
    setProgress(persisted.progress || 0);
    setExecutionLogs(Array.isArray(persisted.executionLogs) ? persisted.executionLogs : []);
    setExecutionStats(persisted.executionStats || null);
    setCurrentRunTaskId(persisted.currentRunTaskId || null);
  }, []);

  const clearRunResults = useCallback(() => {
    setExecutionLogs([]);
    setExecutionStats(null);
    setProgress(0);
  }, []);

  const resetRunState = useCallback(() => {
    runResumeRef.current = false;
    fixRunInFlightRef.current = false;
    fixRunIdempotencyKeyRef.current = null;
    setExecutionLogs([]);
    setExecutionStats(null);
    setProgress(0);
    setExecuting(false);
    setCurrentRunTaskId(null);
    setApprovalOpen(false);
  }, []);

  return {
    addExecutionLog,
    approvalOpen,
    batchSizeLimit,
    clearRunResults,
    concurrencyLimit,
    currentRunTaskId,
    executeFixRun,
    executing,
    executionLogs,
    executionStats,
    persistState,
    progress,
    requestFixRunApproval,
    resetRunState,
    restoreRunState,
    rpmLimit,
    setApprovalOpen,
    setBatchSizeLimit,
    setConcurrencyLimit,
    setCurrentRunTaskId,
    setRpmLimit,
  };
};

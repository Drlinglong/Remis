export const INCREMENTAL_TERMINAL_STATUSES = new Set([
  'completed',
  'partial_failed',
  'failed',
  'cancelled',
  'interrupted',
]);

export const isIncrementalTaskTerminal = (status) => INCREMENTAL_TERMINAL_STATUSES.has(status);

export const shouldResyncIncrementalTask = ({
  currentTaskId,
  currentTaskMode,
  executing,
  loading,
  restorationApplied,
  statusResynced,
}) => Boolean(
  restorationApplied
  && !statusResynced
  && currentTaskId
  && currentTaskMode
  && (loading || executing)
);

export const resyncIncrementalTask = async ({
  connectWebSocket,
  currentTaskId,
  currentTaskMode,
  handleTaskUpdate,
  projectService,
}) => {
  const isPreScan = currentTaskMode === 'pre_scan';

  try {
    const response = await projectService.getTaskStatus(currentTaskId);
    const taskStatus = response.data?.status;

    if (isIncrementalTaskTerminal(taskStatus)) {
      handleTaskUpdate(response.data, isPreScan, 'polling');
      return { source: 'polling', terminal: true };
    }

    connectWebSocket(currentTaskId, isPreScan);
    return { source: 'websocket', terminal: false };
  } catch (error) {
    console.error('Failed to resume incremental task state:', error);
    connectWebSocket(currentTaskId, isPreScan);
    return { source: 'websocket', terminal: false, recoveredFromError: true };
  }
};

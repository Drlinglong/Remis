const TERMINAL_RUN_STATUSES = new Set([
  'completed',
  'partial_failed',
  'failed',
  'cancelled',
  'interrupted',
]);

const defaultWaitForNext = (delayMs) =>
  new Promise((resolve) => setTimeout(resolve, delayMs));

export const pollAgentWorkshopRun = async ({
  taskId,
  getStatus,
  onTask,
  isCancelled = () => false,
  waitForNext = defaultWaitForNext,
  delayMs = 1000,
}) => {
  if (!taskId) throw new Error('Format Repair task ID is required.');

  while (!isCancelled()) {
    await waitForNext(delayMs);
    if (isCancelled()) return null;

    const task = await getStatus(taskId);
    if (!task?.status) {
      throw new Error('Format Repair status response is missing status.');
    }

    onTask(task);
    if (TERMINAL_RUN_STATUSES.has(task.status)) return task;
  }

  return null;
};

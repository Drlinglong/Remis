export const TERMINAL_GLOSSARY_TASK_STATUSES = new Set([
  'completed',
  'failed',
  'cancelled',
  'interrupted',
]);

const defaultWaitForNext = (delayMs) => (
  new Promise((resolve) => window.setTimeout(resolve, delayMs))
);

export const isGlossaryTaskActive = (operation) => Boolean(
  operation?.taskId
  && !TERMINAL_GLOSSARY_TASK_STATUSES.has(operation.status)
  && operation.status !== 'monitor_error'
);

export const pollGlossaryTask = async ({
  taskId,
  getTask,
  onTask,
  isCancelled = () => false,
  waitForNext = defaultWaitForNext,
  delayMs = 1000,
  maxAttempts = 300,
}) => {
  if (!taskId) throw new Error('Glossary task ID is required.');

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (isCancelled()) return null;

    const task = await getTask(taskId);
    if (isCancelled()) return null;
    if (!task?.status) {
      throw new Error('Glossary task status response is missing status.');
    }

    onTask(task);
    if (TERMINAL_GLOSSARY_TASK_STATUSES.has(task.status)) return task;

    await waitForNext(delayMs);
  }

  return null;
};

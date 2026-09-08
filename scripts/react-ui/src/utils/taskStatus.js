export const TERMINAL_TASK_STATUSES = new Set([
  'completed',
  'success',
  'partial_failed',
  'failed',
  'cancelled',
  'canceled',
  'interrupted',
]);

export const isTerminalTaskStatus = (status) => TERMINAL_TASK_STATUSES.has(status);

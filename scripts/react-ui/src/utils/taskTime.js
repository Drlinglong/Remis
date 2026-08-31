const parseTimestamp = (value) => {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
};

export const ACTIVE_TASK_STATUSES = new Set(['queued', 'running', 'awaiting_approval', 'cancelling']);

export const taskDurationMs = (task, now = Date.now()) => {
  const startedAt = parseTimestamp(task?.started_at) ?? parseTimestamp(task?.created_at);
  if (startedAt === null) return null;
  const finishedAt = parseTimestamp(task?.finished_at)
    ?? (ACTIVE_TASK_STATUSES.has(task?.status) ? now : parseTimestamp(task?.updated_at))
    ?? now;
  return Math.max(0, finishedAt - startedAt);
};

export const formatTaskDuration = (milliseconds) => {
  if (!Number.isFinite(milliseconds)) return '--:--:--';
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':');
};

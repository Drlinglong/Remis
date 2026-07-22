export const taskDetailRoute = (taskId) => `/tasks/${encodeURIComponent(String(taskId || ''))}`;

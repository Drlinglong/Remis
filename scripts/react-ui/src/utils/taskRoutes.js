export const taskDetailRoute = (taskId) => `/tasks/${encodeURIComponent(String(taskId || ''))}`;

export const glossaryHealthReviewRoute = (taskId) => `${taskDetailRoute(taskId)}/glossary-health`;

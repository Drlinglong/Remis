export const taskDetailRoute = (taskId) => `/tasks/${encodeURIComponent(String(taskId || ''))}`;

export const glossaryHealthReviewRoute = (taskId) => `${taskDetailRoute(taskId)}/glossary-health`;

export const taskWorkflowTarget = (task = {}) => {
  const pathname = task.source_route === '/glossary'
    ? '/glossary-manager'
    : (task.source_route || '/');
  const state = {
    projectId: task.project_id || task.workflow_context?.project_id || null,
    taskId: task.task_id || null,
    taskMode: task.workflow_context?.mode || null,
  };
  return {
    pathname,
    state: Object.fromEntries(Object.entries(state).filter(([, value]) => value)),
  };
};

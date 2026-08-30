const ACTIONABLE_STATUSES = new Set([
  'queued',
  'running',
  'awaiting_approval',
  'failed',
  'interrupted',
]);

const numberOrNull = (value) => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

export const EMPTY_DASHBOARD_DATA = {
  stats: {
    total_projects: null,
    words_translated: null,
    active_projects: null,
    completion_rate: null,
  },
  charts: { project_status: [], project_distribution: [] },
  recentActivity: [],
};

export function normalizeDashboardData(payload = {}) {
  const sourceStats = payload.stats || {};
  const activeProjects = sourceStats.active_projects ?? sourceStats.active_tasks;
  return {
    stats: {
      total_projects: numberOrNull(sourceStats.total_projects),
      words_translated: numberOrNull(sourceStats.words_translated),
      active_projects: numberOrNull(activeProjects),
      completion_rate: numberOrNull(sourceStats.completion_rate),
    },
    charts: {
      project_status: Array.isArray(payload.charts?.project_status) ? payload.charts.project_status : [],
      project_distribution: Array.isArray(payload.charts?.project_distribution)
        ? payload.charts.project_distribution
        : [],
    },
    recentActivity: Array.isArray(payload.recent_activity) ? payload.recent_activity : [],
  };
}

export function getHomeGreeting(t, hour = new Date().getHours()) {
  const timeKey = hour >= 18 || hour < 5 ? 'evening' : hour >= 12 ? 'afternoon' : 'morning';
  const options = t('homepage_greetings', { returnObjects: true })?.[timeKey];
  return Array.isArray(options) && options.length > 0
    ? options[0]
    : t('homepage_workspace_title');
}

export function getVisibleTasks(tasks = []) {
  const actionable = tasks.filter((task) => ACTIONABLE_STATUSES.has(task.status));
  const latestCompleted = tasks.find((task) => task.status === 'completed');
  return latestCompleted ? [...actionable.slice(0, 2), latestCompleted] : actionable.slice(0, 2);
}

export const isActionableTask = (task) => Boolean(task && ACTIONABLE_STATUSES.has(task.status));

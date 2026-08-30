import { describe, expect, it } from 'vitest';

import {
  getHomeGreeting,
  getVisibleTasks,
  normalizeDashboardData,
} from './homeDashboardModel';

describe('homeDashboardModel', () => {
  it('derives the greeting without owning React state', () => {
    const t = (key, options) => (options?.returnObjects ? {
      morning: ['早上好'],
      afternoon: ['下午好'],
      evening: ['晚上好'],
    } : key);

    expect(getHomeGreeting(t, 8)).toBe('早上好');
    expect(getHomeGreeting(t, 14)).toBe('下午好');
    expect(getHomeGreeting(t, 20)).toBe('晚上好');
  });

  it('normalizes dashboard fallbacks without inventing missing metrics', () => {
    const data = normalizeDashboardData({
      stats: { total_projects: 3, active_tasks: 2 },
      charts: { project_status: [{ name: 'done', value: 1 }] },
      recent_activity: [{ id: 'activity-1' }],
    });

    expect(data.stats).toEqual({
      total_projects: 3,
      words_translated: null,
      active_projects: 2,
      completion_rate: null,
    });
    expect(data.charts.project_distribution).toEqual([]);
    expect(data.recentActivity).toHaveLength(1);
  });

  it('keeps at most two actionable tasks plus the latest completed task', () => {
    const tasks = [
      { task_id: 'queued', status: 'queued' },
      { task_id: 'running', status: 'running' },
      { task_id: 'failed', status: 'failed' },
      { task_id: 'completed', status: 'completed' },
    ];

    expect(getVisibleTasks(tasks).map((task) => task.task_id)).toEqual([
      'queued',
      'running',
      'completed',
    ]);
  });
});

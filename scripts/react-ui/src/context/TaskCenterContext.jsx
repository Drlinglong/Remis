import React, { useCallback, useEffect, useMemo, useState } from 'react';

import api from '../utils/api';
import { TaskCenterContext } from './TaskCenterContextCore';

const REFRESH_INTERVAL_MS = 4000;

export function TaskCenterProvider({ children }) {
  const [tasks, setTasks] = useState([]);
  const [activeCount, setActiveCount] = useState(0);
  const [attentionCount, setAttentionCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [opened, setOpened] = useState(false);

  const refreshTasks = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const [queueResponse, completedResponse] = await Promise.all([
        api.get('/api/tasks', { params: { active_only: true, limit: 200 } }),
        api.get('/api/tasks', { params: { status: 'completed', limit: 1 } }),
      ]);
      const queueTasks = Array.isArray(queueResponse.data?.tasks) ? queueResponse.data.tasks : [];
      const completedTasks = Array.isArray(completedResponse.data?.tasks) ? completedResponse.data.tasks : [];
      const seen = new Set(queueTasks.map((task) => task.task_id));
      setTasks([
        ...queueTasks,
        ...completedTasks.filter((task) => !seen.has(task.task_id)),
      ]);
      setActiveCount(Number(queueResponse.data?.active_count || 0));
      setAttentionCount(Number(queueResponse.data?.attention_count || 0));
    } catch (error) {
      console.error('Failed to refresh task center:', error);
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshTasks();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        refreshTasks({ quiet: true });
      }
    }, REFRESH_INTERVAL_MS);
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') refreshTasks({ quiet: true });
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [refreshTasks]);

  const value = useMemo(() => ({
    activeCount,
    attentionCount,
    loading,
    opened,
    setOpened,
    openTaskCenter: () => setOpened(true),
    closeTaskCenter: () => setOpened(false),
    refreshTasks,
    tasks,
  }), [activeCount, attentionCount, loading, opened, refreshTasks, tasks]);

  return <TaskCenterContext.Provider value={value}>{children}</TaskCenterContext.Provider>;
}

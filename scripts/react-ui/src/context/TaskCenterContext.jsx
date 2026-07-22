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
      const response = await api.get('/api/tasks', { params: { limit: 50 } });
      setTasks(Array.isArray(response.data?.tasks) ? response.data.tasks : []);
      setActiveCount(Number(response.data?.active_count || 0));
      setAttentionCount(Number(response.data?.attention_count || 0));
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

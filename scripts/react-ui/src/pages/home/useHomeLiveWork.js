import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

import { useTaskCenter } from '../../context/TaskCenterContextCore';
import api from '../../utils/api';
import { taskDetailRoute } from '../../utils/taskRoutes';
import { getVisibleTasks, isActionableTask } from './homeDashboardModel';

export function useHomeLiveWork() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { attentionCount = 0, loading: tasksLoading = false, refreshTasks, tasks = [] } = useTaskCenter();
  const [handlingTaskId, setHandlingTaskId] = useState('');
  const [handleError, setHandleError] = useState('');
  const [handleErrorTaskId, setHandleErrorTaskId] = useState('');
  const visibleTasks = useMemo(() => getVisibleTasks(tasks), [tasks]);
  const primaryTask = visibleTasks.find(isActionableTask) || null;

  const openTask = useCallback((task) => {
    navigate(taskDetailRoute(task.task_id));
  }, [navigate]);

  const openProjectManagement = useCallback(() => {
    navigate('/project-management');
  }, [navigate]);

  const openTaskHistory = useCallback(() => {
    navigate('/task-history');
  }, [navigate]);

  const refreshLiveWork = useCallback(() => refreshTasks(), [refreshTasks]);

  const markHandled = useCallback(async (task) => {
    setHandlingTaskId(task.task_id);
    setHandleError('');
    setHandleErrorTaskId('');
    try {
      await api.post(`/api/tasks/${encodeURIComponent(task.task_id)}/archive`);
      await refreshTasks({ quiet: true });
    } catch (error) {
      setHandleError(error.response?.data?.detail || error.message || t('task_center.handle_error'));
      setHandleErrorTaskId(task.task_id);
    } finally {
      setHandlingTaskId('');
    }
  }, [refreshTasks, t]);

  return {
    attentionCount,
    handleError,
    handleErrorTaskId,
    handlingTaskId,
    openProjectManagement,
    openTask,
    openTaskHistory,
    primaryTask,
    refreshLiveWork,
    tasksLoading,
    visibleTasks,
    markHandled,
  };
}

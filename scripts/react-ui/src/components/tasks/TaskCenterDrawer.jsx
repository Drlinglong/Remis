import React, { useMemo, useState } from 'react';
import { Alert, Button, Drawer, Group, Loader, ScrollArea, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconHistory, IconRefresh } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useTaskCenter } from '../../context/TaskCenterContextCore';
import api from '../../utils/api';
import { taskDetailRoute } from '../../utils/taskRoutes';
import { TaskSummaryCard } from './TaskSummaryCard';

function taskActivityTimestamp(task) {
  const value = task.updated_at || task.finished_at || task.started_at || task.created_at;
  const timestamp = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(timestamp) ? timestamp : 0;
}

export function TaskCenterDrawer() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const {
    attentionCount,
    closeTaskCenter,
    loading,
    opened,
    refreshTasks,
    tasks,
  } = useTaskCenter();
  const [handlingTaskId, setHandlingTaskId] = useState('');
  const [handleError, setHandleError] = useState('');
  const visibleTasks = useMemo(() => {
    const newestFirstTasks = [...tasks].sort((left, right) => {
      const recencyDifference = taskActivityTimestamp(right) - taskActivityTimestamp(left);
      return recencyDifference || String(right.task_id).localeCompare(String(left.task_id));
    });
    const actionableTasks = newestFirstTasks.filter((task) => (
      ['queued', 'running', 'awaiting_approval', 'failed', 'interrupted'].includes(task.status)
    ));
    const latestCompletedTask = newestFirstTasks.find((task) => task.status === 'completed');
    const taskQueue = latestCompletedTask
      ? [...actionableTasks, latestCompletedTask]
      : actionableTasks;
    return taskQueue.sort((left, right) => (
      taskActivityTimestamp(right) - taskActivityTimestamp(left)
      || String(right.task_id).localeCompare(String(left.task_id))
    ));
  }, [tasks]);

  const openTask = (task) => {
    closeTaskCenter();
    navigate(taskDetailRoute(task.task_id));
  };

  const openTaskHistory = () => {
    closeTaskCenter();
    navigate('/task-history');
  };

  const markHandled = async (task) => {
    setHandlingTaskId(task.task_id);
    setHandleError('');
    try {
      await api.post(`/api/tasks/${encodeURIComponent(task.task_id)}/archive`);
      await refreshTasks({ quiet: true });
    } catch (error) {
      setHandleError(error.response?.data?.detail || error.message || t('task_center.handle_error'));
    } finally {
      setHandlingTaskId('');
    }
  };

  return (
    <Drawer
      opened={opened}
      onClose={closeTaskCenter}
      position="right"
      size="min(460px, 92vw)"
      title={<Text component="span" fw={700} size="lg">{t('task_center.title')}</Text>}
      overlayProps={{ backgroundOpacity: 0.58, blur: 2 }}
      styles={{ content: { background: 'var(--elevated-bg, var(--surface-bg))', color: 'var(--surface-text-main)' } }}
    >
      <Stack h="calc(100vh - 90px)" gap="md" data-remis-surface="elevated">
        <Group justify="space-between">
          <Text size="sm" c="dimmed">{t('task_center.subtitle')}</Text>
          <Group gap={4} wrap="nowrap">
            <Button
              variant="subtle"
              size="compact-sm"
              leftSection={<IconHistory size={15} />}
              onClick={openTaskHistory}
            >
              {t('task_center.view_history')}
            </Button>
            <Button
              variant="subtle"
              size="compact-sm"
              leftSection={<IconRefresh size={15} />}
              onClick={() => refreshTasks()}
            >
              {t('button_refresh')}
            </Button>
          </Group>
        </Group>
        {handleError && <Alert color="red">{handleError}</Alert>}
        {attentionCount > 0 && (
          <Alert color="orange" icon={<IconAlertTriangle size={18} />}>
            {t('task_center.attention_summary', { count: attentionCount })}
          </Alert>
        )}
        <ScrollArea style={{ flex: 1 }} type="auto">
          {loading ? (
            <Group justify="center" py="xl"><Loader size="sm" /></Group>
          ) : visibleTasks.length > 0 ? (
            <Stack gap="sm" pr="xs">
              {visibleTasks.map((task) => (
                <TaskSummaryCard
                  key={task.task_id}
                  task={task}
                  handling={handlingTaskId === task.task_id}
                  onHandle={markHandled}
                  onOpen={openTask}
                />
              ))}
            </Stack>
          ) : (
            <Stack align="center" py="xl" gap="xs">
              <Text fw={700}>{t('task_center.empty_title')}</Text>
              <Text size="sm" c="dimmed" ta="center">{t('task_center.empty_description')}</Text>
            </Stack>
          )}
        </ScrollArea>
      </Stack>
    </Drawer>
  );
}

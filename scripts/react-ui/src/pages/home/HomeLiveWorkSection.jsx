import React from 'react';
import {
  Alert,
  Button,
  Card,
  Group,
  Skeleton,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconArrowRight,
  IconHistory,
  IconPlayerPlay,
  IconRefresh,
} from '@tabler/icons-react';

import { TaskSummaryCard } from '../../components/tasks/TaskSummaryCard';
import styles from '../HomePage.module.css';

function LiveWorkLoading() {
  return (
    <Stack gap="sm" aria-label="home-live-work-loading">
      {[1, 2].map((item) => (
        <Card key={item} withBorder radius="md" p="sm" data-remis-surface="paper">
          <Skeleton height={16} width="42%" mb="sm" />
          <Skeleton height={12} width="76%" mb="md" />
          <Skeleton height={12} width="52%" />
        </Card>
      ))}
    </Stack>
  );
}

export default function HomeLiveWorkSection({ t, workflow }) {
  const {
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
  } = workflow;
  const hasTasks = visibleTasks.length > 0;

  return (
    <Card
      id="homepage-live-work"
      withBorder
      radius="md"
      p={{ base: 'md', sm: 'lg' }}
      className={styles.liveWork}
      data-remis-surface="surface"
      data-remis-anchor="live-work"
    >
      <Group justify="space-between" align="flex-start" mb="md" gap="md" wrap="wrap">
        <div className={styles.minWidthZero}>
          <Title order={3}>{t('homepage_live_work_title')}</Title>
          <Text size="sm" c="dimmed" className={styles.bodyMeasure}>
            {t('homepage_live_work_subtitle')}
          </Text>
        </div>
        <Group gap={4} wrap="nowrap">
          <Button
            variant="subtle"
            size="compact-sm"
            leftSection={<IconHistory size={15} />}
            data-remis-action="secondary"
            onClick={openTaskHistory}
          >
            {t('task_center.view_history')}
          </Button>
          <Button
            variant="subtle"
            size="compact-sm"
            leftSection={<IconRefresh size={15} />}
            loading={tasksLoading}
            data-remis-action="secondary"
            onClick={refreshLiveWork}
          >
            {t('button_refresh')}
          </Button>
        </Group>
      </Group>

      {attentionCount > 0 && (
        <Alert
          color="orange"
          icon={<IconAlertTriangle size={19} />}
          mb="md"
          data-remis-surface="paper"
          className={styles.attentionAlert}
        >
          {t('task_center.attention_summary', { count: attentionCount })}
        </Alert>
      )}

      {tasksLoading && !hasTasks ? <LiveWorkLoading /> : (
        <Stack gap="sm">
          {hasTasks ? visibleTasks.map((task) => (
            <div key={task.task_id} className={styles.taskRow}>
              <TaskSummaryCard
                compact
                task={task}
                handling={handlingTaskId === task.task_id}
                onHandle={markHandled}
                onOpen={openTask}
              />
              {handleError && handleErrorTaskId === task.task_id && (
                <Alert color="red" mt="xs" data-remis-surface="paper">
                  {handleError}
                </Alert>
              )}
            </div>
          )) : (
            <Stack align="center" justify="center" mih={180} gap="xs" className={styles.emptyState}>
              <Text fw={700}>{t('task_center.empty_title')}</Text>
              <Text size="sm" c="dimmed" ta="center" className={styles.bodyMeasure}>
                {t('homepage_live_work_empty')}
              </Text>
            </Stack>
          )}

          {handleError && !handleErrorTaskId && (
            <Alert color="red" data-remis-surface="paper">{handleError}</Alert>
          )}

          <Group justify={hasTasks ? 'flex-start' : 'center'} mt="xs">
            <Button
              leftSection={primaryTask ? <IconArrowRight size={16} /> : <IconPlayerPlay size={16} />}
              data-remis-action="primary"
              onClick={() => (primaryTask ? openTask(primaryTask) : openProjectManagement())}
            >
              {primaryTask ? t('task_center.view_task') : t('homepage_action_continue_project')}
            </Button>
          </Group>
        </Stack>
      )}
    </Card>
  );
}
